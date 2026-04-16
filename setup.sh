#!/bin/bash
# BearGate setup script - deploy to /opt/beargate
set -e

INSTALL_DIR="/opt/beargate"
SERVICE_NAME="beargate"

echo "🐾 BearGate Setup - Zalo <-> Hermes Gateway"
echo "============================================"

# Check dependencies
echo "[1/6] Kiểm tra dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found"; exit 1; }
command -v openzca >/dev/null 2>&1 || { echo "⚠️  openzca not found - install: npm install -g openzca"; }

# Create install dir
echo "[2/6] Tạo thư mục $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "[3/6] Copy files..."
cp -v main.py config.py listener.py hermes_bridge.py db_local.py db_mariadb.py sync.py "$INSTALL_DIR/"

# Create venv and install deps
echo "[4/6] Tạo Python venv..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r requirements.txt

# Setup .env
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "[5/6] Tạo .env..."
    cp .env.example "$INSTALL_DIR/.env"
    echo "⚠️  Hãy chỉnh $INSTALL_DIR/.env với MariaDB credentials!"
else
    echo "[5/6] .env đã tồn tại, bỏ qua"
fi

# Setup systemd
echo "[6/6] Cài đặt systemd service..."
cp beargate.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ Setup hoàn tất!"
echo ""
echo "Bước tiếp theo:"
echo "  1. Chỉnh $INSTALL_DIR/.env"
echo "  2. systemctl start $SERVICE_NAME"
echo "  3. journalctl -u $SERVICE_NAME -f"
echo ""
