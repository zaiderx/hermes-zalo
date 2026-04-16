# 🐻 Hermes-Zalo

**Zalo <-> Hermes AI Gateway** with MariaDB storage

Kết nối nhiều tài khoản Zalo với Hermes AI agent. Nhận tin nhắn, trả lời tự động, gửi tin nhắn theo lệnh hoặc cron định kỳ.

## Kiến trúc

```
Zalo Users ←──→ openzca (WebSocket)
                    │
              ┌─────┴─────┐
              │ Hermes-Zalo│
              │  Gateway   │
              └─────┬─────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   SQLite DB   MariaDB DB   Hermes AI
   (local)     (optional)   (agent)
                    │
              ┌─────┴─────┐
              │ HTTP API   │  ← Hermes cron gọi qua đây
              │ :8199      │
              └────────────┘
```

## Tính năng

- 🤖 **Multi-account** — chạy nhiều tài khoản Zalo cùng lúc
- 📱 **QR Login** — "đăng nhập zalo với tên X" → scan QR
- 💬 **Tin nhắn tự nhiên** — "gửi cho X qua zalo ..."
- 📸 **Gửi ảnh/file/voice** — "gửi cho X qua zalo ảnh ..."
- ⏰ **Cron gửi định kỳ** — "gửi cho X qua zalo lịch mỗi 1 giờ ..."
- 🔌 **HTTP API** — tích hợp Hermes cron
- 💾 **SQLite + MariaDB** — local cache + persistent storage
- 🛡️ **MariaDB optional** — chạy được chỉ với SQLite

## Cài đặt

### 1. Yêu cầu

- Python 3.10+
- Node.js 22+ với [openzca](https://github.com/darkamenosa/openzca)
- (Optional) MariaDB 10.5+

```bash
# Cài openzca
npm install -g openzca

# Cài Python dependencies
pip install mariadb  # Optional, nếu dùng MariaDB
```

### 2. Deploy

```bash
git clone https://github.com/zaiderx/hermes-zalo.git
cd hermes-zalo

# Cấu hình
cp .env.example .env
nano .env

# Deploy
chmod +x setup.sh
sudo ./setup.sh

# Khởi động
sudo systemctl start hermes-zalo
journalctl -u hermes-zalo -f
```

### 3. Đăng nhập Zalo

```
Anh nhắn: "đăng nhập zalo với tên Duy Phong"
→ Hermes-Zalo gửi QR code
→ Anh scan bằng Zalo trên điện thoại
→ Đã đăng nhập! Zalo ID: xxx
```

Hoặc dùng CLI trên server:

```bash
python cli.py login personal
python cli.py status
python cli.py groups
```

## Sử dụng

### Tin nhắn tự nhiên (gửi qua Telegram/Hermes)

```
"đăng nhập zalo với tên Duy Phong"       → Tạo QR, đăng nhập
"đăng nhập zalo với tên Shop ABC"        → Đăng nhập acc thứ 2
"danh sách acc zalo"                     → Xem các acc đã đăng nhập
"trạng thái zalo"                        → Check login status

"gửi cho Duy Phong qua zalo chào cả nhà"          → Gửi tin nhắn
"gửi cho Duy Phong qua zalo nhóm Công ty báo cáo"  → Gửi vào nhóm cụ thể
"gửi cho Duy Phong qua zalo ảnh https://..."       → Gửi ảnh
"gửi cho Duy Phong qua zalo voice /path/file.ogg"  → Gửi voice
"gửi cho Duy Phong qua zalo file https://..."      → Gửi file

"xem nhóm của Duy Phong"                 → List groups
"đăng xuất zalo tên Duy Phong"           → Logout
```

### Slash commands (qua Zalo DM trực tiếp)

```
/help             → Menu trợ giúp
/login [acc]      → Đăng nhập QR
/logout [acc]     → Đăng xuất
/status           → Trạng thái các acc
/profiles         → Danh sách acc
/groups           → Danh sách nhóm
/allgroups        → Nhóm từ mọi acc
/find <tên>       → Tìm nhóm
/send <nhóm> <msg> → Gửi tin nhắn
/members <nhóm>   → Xem thành viên
/info <nhóm>      → Thông tin nhóm
/me               → Thông tin bot
/ask <câu hỏi>    → Hỏi Hermes AI
```

### Cron gửi định kỳ

```
# Qua tin nhắn tự nhiên
"gửi cho Duy Phong qua zalo lịch mỗi 1 giờ báo cáo tình hình"
"gửi cho Duy Phong qua zalo lịch mỗi 30 phút nhắc việc"
"gửi cho Duy Phong qua zalo lịch hàng ngày 9h chào buổi sáng"
"gửi cho Duy Phong qua zalo lịch 9:00 hàng ngày tổng kết"

# Định dạng lịch hỗ trợ
mỗi N phút          → Interval
mỗi N giờ           → Interval
mỗi 1 ngày          → Interval
hàng ngày           → Daily 08:00
hàng ngày 9h        → Daily 09:00
9:00 hàng ngày      → Daily 09:00
hàng tuần thứ 2     → Weekly Monday 08:00
```

### HTTP API (tích hợp Hermes cron)

Hermes-Zalo chạy HTTP API trên port `8199` (configurable).

```bash
# Gửi tin nhắn
curl -X POST http://localhost:8199/send \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_KEY' \
  -d '{"account": "Duy Phong", "group": "Công ty", "message": "📊 Báo cáo hôm nay..."}'

# Gửi ảnh
curl -X POST http://localhost:8199/send-image \
  -d '{"account": "Duy Phong", "url": "https://...", "caption": "Chart"}'

# Tạo cron job
curl -X POST http://localhost:8199/schedule \
  -d '{"account": "Duy Phong", "message": "Nhắc họp", "schedule": "mỗi 1 giờ"}'

# Xem danh sách acc
curl http://localhost:8199/accounts

# Xem groups của acc
curl http://localhost:8199/accounts/Duy%20Phong/groups

# Health check
curl http://localhost:8199/health
```

**Tích hợp với Hermes cron:**

```
# Trong Hermes chat:
"tạo cron mỗi ngày 9h gửi báo cáo doanh số cho Duy Phong qua zalo nhóm Công ty"

# Hermes sẽ gọi API:
POST http://localhost:8199/send
{"account": "Duy Phong", "group": "Công ty", "message": "📊 Báo cáo..."}
```

## Cấu hình

`.env` file:

```bash
# Zalo profiles (comma-separated)
OPENZCA_PROFILES=personal,work,shop

# Hermes AI
HERMES_API_URL=http://localhost:5000/chat

# SQLite (always used)
SQLITE_PATH=~/.hermes-zalo/hermes_zalo.db

# MariaDB (optional - leave empty to skip)
MARIADB_HOST=
MARIADB_USER=
MARIADB_PASSWORD=

# HTTP API
HERMES_ZALO_API_PORT=8199
HERMES_ZALO_API_KEY=my_secret_key

# Scheduler
SYNC_INTERVAL_MINUTES=15
```

## Cấu trúc dự án

```
hermes-zalo/
├── main.py              # Entry point
├── config.py            # Configuration
├── listener.py          # openzca listener (multi-account)
├── hermes_bridge.py     # Hermes AI bridge
├── nl_parser.py         # Natural language command parser
├── commands.py          # Slash commands
├── zalo_api.py          # Zalo API wrapper (openzca CLI)
├── accounts.py          # Account registry (name → Zalo ID)
├── login.py             # QR login management
├── scheduler.py         # Cron-like job scheduler
├── api_server.py        # HTTP API server
├── db_local.py          # SQLite local cache
├── db_mariadb.py        # MariaDB persistent storage
├── sync.py              # SQLite → MariaDB sync
├── cli.py               # CLI tool
├── hermes-zalo.service  # Systemd service
├── setup.sh             # Deploy script
├── setup_mariadb.sql    # MariaDB schema
├── .env.example         # Config template
└── requirements.txt     # Python dependencies
```

## Flow hoạt động

### 1. Nhận tin nhắn
```
Zalo user → openzca WebSocket → hermes-zalo listener
    → Save to SQLite
    → Save to MariaDB (nếu có)
    → Parse NL command?
        → Có → Execute command
        → Không → Forward to Hermes AI → Reply
```

### 2. Gửi tin nhắn (qua lệnh)
```
User: "gửi cho Duy Phong qua zalo báo cáo..."
    → nl_parser: find account "Duy Phong"
    → accounts.json: profile = "account_duy_phong"
    → zalo_api.send_message(profile="account_duy_phong")
    → openzca msg send <groupId> "báo cáo..." -g
```

### 3. Cron gửi định kỳ
```
scheduler.py: job loop
    → wait until schedule time
    → zalo_api.send_message()
    → save stats
    → loop
```

### 4. Hermes cron integration
```
Hermes cron job fires
    → curl POST http://localhost:8199/send
    → api_server.py: find account + group
    → zalo_api.send_message()
    → return success/error
```

## MariaDB Schema

```sql
chat_logs (
    id, thread_id, msg_id, sender_id, sender_name,
    content, msg_type, chat_type, timestamp, timestamp_ms,
    is_from_self, raw_json, created_at
)
```

## License

MIT
