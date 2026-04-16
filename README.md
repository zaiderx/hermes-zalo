# 🐻 BearGate

**Zalo <-> Hermes Gateway** with MariaDB storage

BearGate bridge Zalo messages to Hermes AI agent, with MariaDB for persistent storage.

## Architecture

```
Zalo User → openzca listen (WebSocket)
    → BearGate listener
        → SQLite (local cache)
        → MariaDB (persistent storage)
        → Hermes Bridge → AI Agent
    → openzca msg send → Zalo User
```

## Quick Start

```bash
# 1. Setup MariaDB
mysql -u root -p < setup_mariadb.sql

# 2. Configure
cp .env.example .env
nano .env  # Edit MariaDB credentials

# 3. Deploy
chmod +x setup.sh
sudo ./setup.sh

# 4. Start
sudo systemctl start hermes-zalo
journalctl -u hermes-zalo -f
```

## Requirements

- Python 3.10+
- Node.js 22+ with openzca (`npm install -g openzca`)
- MariaDB 10.5+
- libmariadb-dev (`apt install libmariadb-dev`)

## Configuration

All config via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENZCA_PROFILE` | default | Zalo profile name |
| `OWN_ID` | (auto) | Own Zalo ID for filtering |
| `HERMES_API_URL` | http://localhost:5000/chat | Hermes API endpoint |
| `MARIADB_HOST` | localhost | MariaDB host |
| `MARIADB_DATABASE` | hermes-zalo | Database name |
| `SYNC_INTERVAL_MINUTES` | 15 | SQLite→MariaDB sync interval |

## Project Structure

```
hermes-zalo/
├── main.py              # Entry point
├── config.py            # Configuration from env
├── listener.py          # openzca listen wrapper
├── hermes_bridge.py     # Hermes API bridge
├── db_local.py          # SQLite local cache
├── db_mariadb.py        # MariaDB persistent storage
├── sync.py              # Auto-sync SQLite → MariaDB
├── hermes-zalo.service     # Systemd service
├── setup.sh             # Deploy script
├── setup_mariadb.sql    # MariaDB setup SQL
├── .env.example         # Environment template
└── requirements.txt     # Python dependencies
```

## Flow

1. `openzca listen --raw --keep-alive` streams JSON messages
2. BearGate parses each line, filters own messages
3. Saves to SQLite (fast) + MariaDB (persistent)
4. DMs forwarded to Hermes agent
5. Response sent back via `openzca msg send`
6. Auto-sync every 15 min syncs SQLite → MariaDB

## MariaDB Schema

```sql
chat_logs (
    id, thread_id, msg_id, sender_id, sender_name,
    content, msg_type, chat_type, timestamp, timestamp_ms,
    is_from_self, raw_json, created_at
)
```
