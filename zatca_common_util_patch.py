#!/usr/bin/env python3
"""
Patch ZATCA common_util.py - v2

Auto-create VAT accounts and templates on the fly if missing,
instead of throwing error. This handles the Demo Company case
where the company is created automatically by demo data without VAT setup.
"""

import sys
import os

PATH = "/home/frappe/frappe-bench/apps/zatca_integration/zatca_integration/common_util.py"

# We will replace the entire validate_sales_invoice function
NEW_FUNCTION = '''def validate_sales_invoice(doc, method):
    if not doc.taxes_and_charges:
        # Try to find existing default Sales Tax Template
        default_tax = frappe.db.get_value(
            "Sales Taxes and Charges Template",
            {"company": doc.company, "is_default": 1},
            "name"
        )

        # If not found, try ANY template for this company
        if not default_tax:
            default_tax = frappe.db.get_value(
                "Sales Taxes and Charges Template",
                {"company": doc.company},
                "name"
            )

        # If still nothing, auto-create Saudi VAT 15% on the fly
        if not default_tax:
            default_tax = _auto_create_saudi_vat(doc.company)

        if default_tax:
            doc.taxes_and_charges = default_tax
            from erpnext.controllers.accounts_controller import get_taxes_and_charges
            taxes = get_taxes_and_charges("Sales Taxes and Charges Template", default_tax)
            doc.set("taxes", [])
            for t in taxes:
                doc.append("taxes", t)
        else:
            frappe.throw("Sales Taxes and Charges Template must be provided.")

    if doc.is_return and (not doc.return_against and not doc.custom_cn_ref):
        frappe.throw("Go to credit note details and fetch return invoices")


def _auto_create_saudi_vat(company_name):
    """Auto-create Saudi VAT 15% account and template for a company."""
    abbr = frappe.db.get_value("Company", company_name, "abbr")
    if not abbr:
        return None

    # Find parent account
    parent = None
    for c in [f"Duties and Taxes - {abbr}", f"Tax Assets - {abbr}"]:
        if frappe.db.exists("Account", c):
            parent = c
            break
    if not parent:
        for pattern in [f"%Duties and Taxes - {abbr}", f"%Tax Assets - {abbr}"]:
            r = frappe.db.get_value(
                "Account",
                {"name": ["like", pattern], "company": company_name, "is_group": 1},
                "name"
            )
            if r:
                parent = r
                break
    if not parent:
        parent = frappe.db.get_value(
            "Account",
            {"company": company_name, "is_group": 1, "root_type": "Liability"},
            "name"
        )
    if not parent:
        return None

    # Create VAT 15% account
    vat_account_name = f"VAT 15% - {abbr}"
    if not frappe.db.exists("Account", vat_account_name):
        try:
            frappe.get_doc({
                "doctype": "Account",
                "account_name": "VAT 15%",
                "parent_account": parent,
                "company": company_name,
                "account_type": "Tax",
                "tax_rate": 15.0,
                "is_group": 0,
            }).insert(ignore_permissions=True)
        except Exception:
            return None

    # Create Sales Tax Template
    template_name = f"Saudi VAT 15% - {abbr}"
    if not frappe.db.exists("Sales Taxes and Charges Template", template_name):
        try:
            frappe.get_doc({
                "doctype": "Sales Taxes and Charges Template",
                "title": "Saudi VAT 15%",
                "company": company_name,
                "is_default": 1,
                "taxes": [{
                    "charge_type": "On Net Total",
                    "account_head": vat_account_name,
                    "description": "VAT 15%",
                    "rate": 15.0,
                }],
            }).insert(ignore_permissions=True)
        except Exception:
            return None

    # Set cost center if not set
    cc = frappe.db.get_value("Company", company_name, "round_off_cost_center")
    if not cc:
        cc = frappe.db.get_value("Cost Center", {"company": company_name, "is_group": 0}, "name")
        if cc:
            frappe.db.set_value("Company", company_name, "round_off_cost_center", cc)
            frappe.db.set_value("Company", company_name, "depreciation_cost_center", cc)

    frappe.db.commit()

    # Return the actual template name (might have suffix)
    return frappe.db.get_value(
        "Sales Taxes and Charges Template",
        {"company": company_name, "title": "Saudi VAT 15%"},
        "name"
    )'''


def main():
    if not os.path.exists(PATH):
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    with open(PATH, "r") as f:
        content = f.read()

    # Marker to detect if v2 patch is applied
    if "_auto_create_saudi_vat" in content:
        print("Already patched (v2), skipping")
        return

    # Find the validate_sales_invoice function and replace it entirely
    # We need to find from "def validate_sales_invoice" to the next "def "
    import re

    pattern = re.compile(
        r'def validate_sales_invoice\(doc, method\):.*?(?=\ndef [a-zA-Z_])',
        re.DOTALL
    )

    if not pattern.search(content):
        print("ERROR: Could not find validate_sales_invoice function")
        sys.exit(1)

    new_content = pattern.sub(NEW_FUNCTION + "\n\n\n", content)

    with open(PATH, "w") as f:
        f.write(new_content)

    print("Successfully patched common_util.py (v2)")


if __name__ == "__main__":
    main()
