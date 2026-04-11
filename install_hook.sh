#!/bin/bash
# install_hook.sh — installs all ZATCA patches + industry field
# Fixed: Python patch scripts are now EXECUTED, not copied as files
set -e

BENCH_PATH="/home/frappe/frappe-bench"
ZATCA_APP="$BENCH_PATH/apps/zatca_integration/zatca_integration"
FRAPPE_UTILS="$BENCH_PATH/apps/frappe/frappe/utils"
REPO_PATH="$(dirname "$(readlink -f "$0")")"

echo "=== Installing ZATCA Hook + All Patches ==="

echo "[1/9] Copying setup_wizard_hook.py..."
sudo cp "$REPO_PATH/setup_wizard_hook.py" "$ZATCA_APP/setup_wizard_hook.py"
echo "  Done"

echo "[2/9] Updating hooks.py..."
HOOKS_FILE="$ZATCA_APP/hooks.py"
if grep -q "setup_wizard_complete" "$HOOKS_FILE"; then
    echo "  Hook already exists"
else
    echo '
setup_wizard_complete = "zatca_integration.setup_wizard_hook.after_wizard_complete"
' | sudo tee -a "$HOOKS_FILE" > /dev/null
    echo "  Added"
fi

echo "[3/9] Running common_util.py patch..."
if [ -f "$REPO_PATH/zatca_common_util_patch.py" ]; then
    sudo python3 "$REPO_PATH/zatca_common_util_patch.py" || echo "  Patch reported error (may be already applied)"
else
    echo "  Skipped (patch file missing)"
fi

echo "[4/9] Running zatca_vat.py report patch..."
if [ -f "$REPO_PATH/zatca_vat_report_patch.py" ]; then
    sudo python3 "$REPO_PATH/zatca_vat_report_patch.py" || echo "  Patch reported error (may be already applied)"
else
    echo "  Skipped (patch file missing)"
fi

echo "[5/9] Installing print format setup script..."
sudo cp "$REPO_PATH/zatca_print_format_setup.py" "$FRAPPE_UTILS/_zatca_pf_setup.py"
echo "  Done"

echo "[6/9] Installing industry field setup script..."
sudo cp "$REPO_PATH/add_industry_field.py" "$FRAPPE_UTILS/_add_industry_field.py"
sudo cp "$REPO_PATH/fix_zatca_links.py" "$FRAPPE_UTILS/_fix_zatca_links.py"
echo "  Done"

echo "[7/9] Fixing permissions..."
sudo chown -R frappe:frappe "$ZATCA_APP"
sudo chown frappe:frappe "$FRAPPE_UTILS/_zatca_pf_setup.py" "$FRAPPE_UTILS/_add_industry_field.py" "$FRAPPE_UTILS/_fix_zatca_links.py"
echo "  Done"

echo "[8/9] Applying patches and clearing cache for all sites..."
cd "$BENCH_PATH"
for site in $(ls sites/ | grep -v common_site_config); do
    if [ -f "sites/$site/site_config.json" ]; then
        sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site execute frappe.utils._add_industry_field.run" 2>&1 || true
        sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site execute frappe.utils._zatca_pf_setup.run" 2>&1 || true
        sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site execute frappe.utils._fix_zatca_links.run" 2>&1 || true
        sudo -u frappe bash -c "cd $BENCH_PATH && /home/frappe/.local/bin/bench --site $site clear-cache" 2>&1 || true
        echo "  Processed: $site"
    fi
done

echo "[9/9] Restarting services..."
sudo supervisorctl restart frappe-bench-web:
sudo supervisorctl restart frappe-bench-workers:
echo "  Done"

echo ""
echo "=== Installation Complete! ==="
echo "Patches applied:"
echo "  1. Setup Wizard Hook  - VAT + ZATCA + Industry customizations"
echo "  2. common_util Patch  - auto-assign default tax to invoices"
echo "  3. ZATCA VAT Report   - skip Expense Claim if HRMS missing"
echo "  4. Print Format       - 'Zatca PDF-A 3B Custom' with QR code"
echo "  5. Industry Field     - 'custom_industry_type' on Company + Construction type"
echo ""
echo "All new sites will have these fixes automatically."
