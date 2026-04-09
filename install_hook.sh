#!/bin/bash
# ===================================================================
# Install ZATCA Setup Wizard Hook + All Patches + Print Format
# ===================================================================
# This script installs:
#   1. setup_wizard_hook.py (auto VAT + ZATCA enable on company)
#   2. common_util.py patch (auto tax template on invoices)
#   3. zatca_vat.py patch (skip Expense Claim if HRMS not installed)
#   4. zatca_print_format_setup.py (creates Custom print format with QR)
# ===================================================================

set -e

BENCH_PATH="/home/frappe/frappe-bench"
ZATCA_APP="$BENCH_PATH/apps/zatca_integration/zatca_integration"
FRAPPE_UTILS="$BENCH_PATH/apps/frappe/frappe/utils"

echo "=== Installing ZATCA Hook + All Patches ==="

# Step 1: Copy hook file
echo "[1/8] Copying setup_wizard_hook.py..."
cp setup_wizard_hook.py "$ZATCA_APP/setup_wizard_hook.py"
echo "  Done"

# Step 2: Add hook to hooks.py
echo "[2/8] Updating hooks.py..."
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
echo "[3/8] Patching common_util.py..."
python3 zatca_common_util_patch.py
echo "  Done"

# Step 4: Patch zatca_vat.py report
echo "[4/8] Patching zatca_vat.py report..."
python3 zatca_vat_report_patch.py
echo "  Done"

# Step 5: Install print format setup script
echo "[5/8] Installing print format setup script..."
cp zatca_print_format_setup.py "$FRAPPE_UTILS/_zatca_pf_setup.py"
chown frappe:frappe "$FRAPPE_UTILS/_zatca_pf_setup.py"
echo "  Done"

# Step 6: Fix ownership
echo "[6/8] Fixing permissions..."
chown -R frappe:frappe "$BENCH_PATH/apps/zatca_integration/"
echo "  Done"

# Step 7: Apply print format to all existing sites + clear cache
echo "[7/8] Applying print format and clearing cache for all sites..."
SITES=$(ls "$BENCH_PATH/sites/" | grep -v "^\\." | grep -v "^assets$" | grep -v "^apps")
for site in $SITES; do
    sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site execute frappe.utils._zatca_pf_setup.run" 2>/dev/null || true
    sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site clear-cache" 2>/dev/null || true
    echo "  Processed: $site"
done

# Step 8: Restart services
echo "[8/8] Restarting services..."
systemctl restart erpnext-provision 2>/dev/null || true
sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench restart" 2>/dev/null || true
echo "  Done"

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Patches applied:"
echo "  1. Setup Wizard Hook  - auto VAT + enable ZATCA on company"
echo "  2. common_util Patch  - auto-assign default tax to invoices"
echo "  3. ZATCA VAT Report   - skip Expense Claim if HRMS missing"
echo "  4. Print Format       - 'Zatca PDF-A 3B Custom' with QR code"
echo ""
echo "All new sites will have these fixes automatically."
