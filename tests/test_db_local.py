"""Tests for db_local module."""

import pytest
import db_local
import config


class TestDBLocal:
    def test_init_creates_tables(self):
        conn = db_local.get_conn()
        assert conn is not None

        # Check tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_logs'"
        )
        assert cursor.fetchone() is not None

    def test_insert_message(self):
        data = {
            "threadId": "12345",
            "msgId": "msg001",
            "senderId": "999",
            "senderName": "Test User",
            "content": "Hello world",
            "msgType": "text",
            "chatType": "user",
            "timestamp": 1700000000,
            "ts": 1700000000000,
        }
        row_id = db_local.insert_message(data)
        assert row_id > 0

    def test_get_unsynced_messages(self):
        data = {
            "threadId": "12345",
            "senderId": "999",
            "content": "Test message",
        }
        db_local.insert_message(data)

        unsynced = db_local.get_unsynced_messages()
        assert len(unsynced) >= 1
        assert unsynced[0]["synced"] == 0

    def test_mark_synced(self):
        data = {
            "threadId": "12345",
            "senderId": "999",
            "content": "Sync test",
        }
        row_id = db_local.insert_message(data)

        db_local.mark_synced([row_id])

        unsynced = db_local.get_unsynced_messages()
        synced_ids = [r["id"] for r in unsynced]
        assert row_id not in synced_ids

    def test_get_stats(self):
        data = {
            "threadId": "12345",
            "senderId": "999",
            "content": "Stats test",
        }
        db_local.insert_message(data)

        stats = db_local.get_stats()
        assert stats["total"] >= 1
        assert "unsynced" in stats

    def test_is_from_self_detection(self, monkeypatch):
        monkeypatch.setattr(config, "OWN_ID", "999")

        data = {
            "threadId": "12345",
            "senderId": "999",
            "content": "Self message",
        }
        row_id = db_local.insert_message(data)

        conn = db_local.get_conn()
        row = conn.execute("SELECT is_from_self FROM chat_logs WHERE id = ?", (row_id,)).fetchone()
        assert row["is_from_self"] == 1

    def test_transaction_rollback(self):
        """Test that transactions rollback on error."""
        try:
            with db_local.transaction() as conn:
                conn.execute(
                    "INSERT INTO chat_logs (thread_id, sender_id, content, created_at) VALUES (?, ?, ?, 0)",
                    ("t1", "s1", "test"),
                )
                raise ValueError("Force rollback")
        except ValueError:
            pass

        # The insert should have been rolled back
        conn = db_local.get_conn()
        rows = conn.execute(
            "SELECT * FROM chat_logs WHERE thread_id = 't1' AND content = 'test'"
        ).fetchall()
        assert len(rows) == 0
