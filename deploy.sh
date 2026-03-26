#!/bin/bash
# ===================================================================
# ERPNext SaaS Provisioning - Deploy from GitHub
# ===================================================================
# Usage: curl -sL https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/deploy.sh | bash
# Or:    ./deploy.sh
# ===================================================================

set -e

INSTALL_DIR="/home/frappe/erpnext-saas-provisioning"
BENCH_PATH="/home/frappe/frappe-bench"

echo ""
echo "=== ERPNext SaaS Provisioning - Deploy ==="
echo ""

# Step 1: Copy app.py
echo "[1/4] Updating app.py..."
cp app.py "$INSTALL_DIR/app.py"

# Step 2: Copy .env.example if .env doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "[2/4] Creating .env from example..."
    cp .env.example "$INSTALL_DIR/.env"
    API_KEY=$(python3 -c "import uuid; print(uuid.uuid4())")
    sed -i "s/change-me-in-production/$API_KEY/" "$INSTALL_DIR/.env"
    echo "  API Key: $API_KEY"
else
    echo "[2/4] .env exists, skipping..."
fi

# Step 3: Install dependencies
echo "[3/4] Installing dependencies..."
pip3 install flask python-dotenv gunicorn requests --break-system-packages -q 2>/dev/null || \
pip3 install flask python-dotenv gunicorn requests -q

# Step 4: Setup systemd service if not exists
if [ ! -f /etc/systemd/system/erpnext-provision.service ]; then
    echo "[4/4] Creating systemd service..."
    cat > /etc/systemd/system/erpnext-provision.service << 'EOF'
[Unit]
Description=ERPNext SaaS Provisioning API
After=network.target mariadb.service nginx.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/frappe/erpnext-saas-provisioning
EnvironmentFile=/home/frappe/erpnext-saas-provisioning/.env
ExecStart=/usr/local/bin/gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 600 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable erpnext-provision
else
    echo "[4/4] Service exists, restarting..."
fi

# Restart service
systemctl restart erpnext-provision
sleep 2

if systemctl is-active --quiet erpnext-provision; then
    echo ""
    echo "=== Deploy successful! Service is running ==="
    echo ""
    curl -s http://localhost:5000/api/health | python3 -m json.tool
else
    echo ""
    echo "=== ERROR: Service failed to start ==="
    journalctl -u erpnext-provision -n 20 --no-pager
fi
