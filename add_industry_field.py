#!/usr/bin/env python3
"""
Add custom_industry_type Link field to Company DocType.

Installed at:
    /home/frappe/frappe-bench/apps/frappe/frappe/utils/_add_industry_field.py

Run on each site via:
    bench --site SITENAME execute frappe.utils._add_industry_field.run
"""

import frappe


def run():
    """Add custom_industry_type field to Company if not exists."""
    fieldname = "custom_industry_type"
    doctype = "Company"

    existing = frappe.db.exists(
        "Custom Field",
        {"dt": doctype, "fieldname": fieldname}
    )

    if existing:
        print(f"Field {fieldname} already exists on {doctype}")
        return

    try:
        cf = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": doctype,
            "fieldname": fieldname,
            "label": "Industry Type",
            "fieldtype": "Link",
            "options": "Industry Type",
            "insert_after": "country",
            "description": "Used for industry-specific customizations (Construction, Real Estate, etc.)",
        })
        cf.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache()
        print(f"Created {fieldname} on {doctype}")
    except Exception as e:
        print(f"Error: {e}")
