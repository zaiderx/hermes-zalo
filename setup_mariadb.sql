-- Hermes-Zalo MariaDB setup
-- Run: mysql -u root -p < setup_mariadb.sql

CREATE DATABASE IF NOT EXISTS hermes_zalo
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'hermes_zalo'@'localhost' IDENTIFIED BY 'CHANGE_ME_PASSWORD';
GRANT ALL PRIVILEGES ON hermes_zalo.* TO 'hermes_zalo'@'localhost';
FLUSH PRIVILEGES;

USE hermes_zalo;

CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(64) NOT NULL,
    msg_id VARCHAR(64),
    sender_id VARCHAR(64) NOT NULL,
    sender_name VARCHAR(255),
    content TEXT NOT NULL,
    msg_type VARCHAR(32) DEFAULT 'text',
    chat_type VARCHAR(16) DEFAULT 'user',
    timestamp BIGINT,
    timestamp_ms BIGINT,
    is_from_self TINYINT(1) DEFAULT 0,
    raw_json LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_thread (thread_id),
    INDEX idx_sender (sender_id),
    INDEX idx_ts (timestamp_ms),
    INDEX idx_chat_type (chat_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sync_state (
    `key` VARCHAR(128) PRIMARY KEY,
    `value` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Stats view
CREATE OR REPLACE VIEW v_stats AS
SELECT
    COUNT(*) as total_messages,
    SUM(CASE WHEN chat_type = 'user' THEN 1 ELSE 0 END) as dm_count,
    SUM(CASE WHEN chat_type = 'group' THEN 1 ELSE 0 END) as group_count,
    SUM(CASE WHEN is_from_self = 1 THEN 1 ELSE 0 END) as self_messages,
    MIN(created_at) as first_message,
    MAX(created_at) as last_message
FROM chat_logs;
