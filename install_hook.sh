#!/bin/bash
# ===================================================================
# Install ZATCA Setup Wizard Hook + All Patches
# ===================================================================
# This script installs:
#   1. setup_wizard_hook.py (auto VAT after wizard)
#   2. common_util.py patch (auto tax template on invoices)
#   3. zatca_vat.py patch (skip Expense Claim if HRMS not installed)
# ===================================================================

set -e

BENCH_PATH="/home/frappe/frappe-bench"
ZATCA_APP="$BENCH_PATH/apps/zatca_integration/zatca_integration"

echo "=== Installing ZATCA Hook + All Patches ==="

# Step 1: Copy hook file
echo "[1/7] Copying setup_wizard_hook.py..."
cp setup_wizard_hook.py "$ZATCA_APP/setup_wizard_hook.py"
echo "  Done"

# Step 2: Add hook to hooks.py
echo "[2/7] Updating hooks.py..."
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
echo "[3/7] Patching common_util.py..."
python3 zatca_common_util_patch.py
echo "  Done"

# Step 4: Patch zatca_vat.py report
echo "[4/7] Patching zatca_vat.py report..."
python3 zatca_vat_report_patch.py
echo "  Done"

# Step 5: Fix ownership
echo "[5/7] Fixing permissions..."
chown -R frappe:frappe "$BENCH_PATH/apps/zatca_integration/"
echo "  Done"

# Step 6: Clear cache for all sites
echo "[6/7] Clearing cache..."
SITES=$(ls "$BENCH_PATH/sites/" | grep -v "^\\." | grep -v "^assets$" | grep -v "^apps")
for site in $SITES; do
    sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site clear-cache" 2>/dev/null || true
    echo "  Cleared: $site"
done

# Step 7: Restart services
echo "[7/7] Restarting services..."
systemctl restart erpnext-provision 2>/dev/null || true
sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench restart" 2>/dev/null || true
echo "  Done"

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Patches applied:"
echo "  1. Setup Wizard Hook  - auto VAT after wizard completes"
echo "  2. common_util Patch  - auto-assign default tax to invoices"
echo "  3. ZATCA VAT Report   - skip Expense Claim if HRMS missing"
echo ""
echo "All new sites will have these fixes automatically."
