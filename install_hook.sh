#!/bin/bash
# ===================================================================
# Install ZATCA Setup Wizard Hook + common_util.py Patch
# ===================================================================
# This script:
#   1. Installs setup_wizard_hook.py (auto VAT after wizard)
#   2. Patches common_util.py (auto-assign default tax template)
#   3. Restarts services
# ===================================================================

set -e

BENCH_PATH="/home/frappe/frappe-bench"
ZATCA_APP="$BENCH_PATH/apps/zatca_integration/zatca_integration"

echo "=== Installing ZATCA Setup Wizard Hook + common_util Patch ==="

# Step 1: Copy hook file
echo "[1/6] Copying setup_wizard_hook.py..."
cp setup_wizard_hook.py "$ZATCA_APP/setup_wizard_hook.py"
echo "  Done"

# Step 2: Add hook to hooks.py if not exists
echo "[2/6] Updating hooks.py..."
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

# Step 3: Patch common_util.py
echo "[3/6] Patching common_util.py..."
python3 zatca_common_util_patch.py
echo "  Done"

# Step 4: Fix ownership
echo "[4/6] Fixing permissions..."
chown -R frappe:frappe "$BENCH_PATH/apps/zatca_integration/"
echo "  Done"

# Step 5: Clear cache for all sites
echo "[5/6] Clearing cache..."
SITES=$(ls "$BENCH_PATH/sites/" | grep -v "^\\." | grep -v "^assets$" | grep -v "^apps")
for site in $SITES; do
    sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site clear-cache" 2>/dev/null || true
    echo "  Cleared: $site"
done

# Step 6: Restart services
echo "[6/6] Restarting services..."
systemctl restart erpnext-provision 2>/dev/null || true
sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench restart" 2>/dev/null || true
echo "  Done"

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "What was installed:"
echo "  1. Setup Wizard Hook  - auto VAT after client completes wizard"
echo "  2. common_util Patch  - auto-assign default tax to invoices"
echo ""
echo "Now any new site will:"
echo "  - Auto-create VAT accounts after Setup Wizard"
echo "  - Auto-create Sales/Purchase tax templates"
echo "  - Auto-link ZATCA settings"
echo "  - Allow demo data installation without errors"
echo ""
echo "Test by creating a new site and completing Setup Wizard"
echo "with 'Generate Demo Data' checked."
