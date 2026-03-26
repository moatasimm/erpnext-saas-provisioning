#!/bin/bash
# ===================================================================
# Install ZATCA Setup Wizard Hook
# Adds auto VAT setup when client completes Setup Wizard
# ===================================================================

set -e

BENCH_PATH="/home/frappe/frappe-bench"
ZATCA_APP="$BENCH_PATH/apps/zatca_integration/zatca_integration"

echo "=== Installing ZATCA Setup Wizard Hook ==="

# Step 1: Copy hook file
echo "[1/5] Copying setup_wizard_hook.py..."
cp setup_wizard_hook.py "$ZATCA_APP/setup_wizard_hook.py"
echo "  Done"

# Step 2: Add hook to hooks.py if not exists
echo "[2/5] Updating hooks.py..."
if ! grep -q "setup_wizard_complete" "$ZATCA_APP/hooks.py"; then
    cat >> "$ZATCA_APP/hooks.py" << 'HOOKEOF'

# Auto Saudi VAT setup after Setup Wizard
setup_wizard_complete = [
    "zatca_integration.setup_wizard_hook.after_wizard_complete"
]
HOOKEOF
    echo "  Hook added"
else
    echo "  Hook already exists"
fi

# Step 3: Fix ownership
echo "[3/5] Fixing permissions..."
chown -R frappe:frappe "$BENCH_PATH/apps/zatca_integration/"
echo "  Done"

# Step 4: Clear cache for all sites
echo "[4/5] Clearing cache..."
SITES=$(ls "$BENCH_PATH/sites/" | grep -v "^\\." | grep -v "^assets$")
for site in $SITES; do
    sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site clear-cache" 2>/dev/null || true
    echo "  Cleared: $site"
done

# Step 5: Restart services
echo "[5/5] Restarting services..."
systemctl restart erpnext-provision 2>/dev/null || true
sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench restart" 2>/dev/null || true
echo "  Done"

echo ""
echo "=== Hook Installed Successfully! ==="
echo ""
echo "Now when any client completes Setup Wizard:"
echo "  - VAT accounts (15%, Zero, Exempt) auto-created"
echo "  - Sales & Purchase tax templates auto-created"
echo "  - ZATCA settings auto-linked"
echo ""
echo "Test: delete demoerp, create new, complete wizard"
echo "  VAT should appear automatically!"
