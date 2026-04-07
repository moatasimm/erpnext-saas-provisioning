#!/usr/bin/env python3
"""
Patch ZATCA common_util.py to auto-assign default Sales Tax Template
instead of throwing error when missing.

This allows demo data and any invoice without explicit tax to work
by automatically using the company's default Sales Taxes Template.
"""

import sys
import os

PATH = "/home/frappe/frappe-bench/apps/zatca_integration/zatca_integration/common_util.py"

OLD_CODE = '''def validate_sales_invoice(doc, method):
    if not doc.taxes_and_charges:
        frappe.throw("Sales Taxes and Charges Template must be provided.")'''

NEW_CODE = '''def validate_sales_invoice(doc, method):
    if not doc.taxes_and_charges:
        # Auto-assign default Sales Tax Template if exists
        default_tax = frappe.db.get_value(
            "Sales Taxes and Charges Template",
            {"company": doc.company, "is_default": 1},
            "name"
        )
        if default_tax:
            doc.taxes_and_charges = default_tax
            # Apply taxes from template
            from erpnext.controllers.accounts_controller import get_taxes_and_charges
            taxes = get_taxes_and_charges("Sales Taxes and Charges Template", default_tax)
            doc.set("taxes", [])
            for t in taxes:
                doc.append("taxes", t)
        else:
            frappe.throw("Sales Taxes and Charges Template must be provided.")'''


def main():
    if not os.path.exists(PATH):
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    with open(PATH, "r") as f:
        content = f.read()

    if "Auto-assign default Sales Tax Template" in content:
        print("Already patched, skipping")
        return

    if OLD_CODE not in content:
        print("ERROR: Original code pattern not found. ZATCA version may differ.")
        sys.exit(1)

    content = content.replace(OLD_CODE, NEW_CODE)

    with open(PATH, "w") as f:
        f.write(content)

    print("Successfully patched common_util.py")


if __name__ == "__main__":
    main()
