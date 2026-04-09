#!/usr/bin/env python3
"""
Patch ZATCA VAT report to skip Expense Claim query when HRMS is not installed.
Prevents: pymysql.err.ProgrammingError: Table 'tabExpense Claim' doesn't exist
"""

import sys
import os

PATH = (
    "/home/frappe/frappe-bench/apps/zatca_integration/zatca_integration/"
    "saudi_arabia_electronic_invoicing/report/zatca_vat/zatca_vat.py"
)

OLD = '''def get_expense_claim_vat_by_type(company, from_date, to_date):
    """Return VAT from Expense Claims grouped by Account.custom_tax_type.
    Expense Claims are always treated as purchases (input VAT).
    """
    if not from_date or not to_date:
        return {}'''

NEW = '''def get_expense_claim_vat_by_type(company, from_date, to_date):
    """Return VAT from Expense Claims grouped by Account.custom_tax_type.
    Expense Claims are always treated as purchases (input VAT).
    """
    if not from_date or not to_date:
        return {}
    # Skip if HRMS (Expense Claim) is not installed
    if not frappe.db.exists("DocType", "Expense Claim"):
        return {}'''


def main():
    if not os.path.exists(PATH):
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    with open(PATH, "r") as f:
        content = f.read()

    if 'if not frappe.db.exists("DocType", "Expense Claim")' in content:
        print("Already patched, skipping")
        return

    if OLD not in content:
        print("ERROR: Pattern not found in zatca_vat.py")
        sys.exit(1)

    content = content.replace(OLD, NEW)

    with open(PATH, "w") as f:
        f.write(content)

    print("Successfully patched zatca_vat.py")


if __name__ == "__main__":
    main()
