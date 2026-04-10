#!/usr/bin/env python3
"""
Add custom_industry_type field on Company + ensure Construction industry exists.

Installed at:
    /home/frappe/frappe-bench/apps/frappe/frappe/utils/_add_industry_field.py

Run on each site via:
    bench --site SITENAME execute frappe.utils._add_industry_field.run
"""

import frappe


def run():
    _add_custom_field()
    _ensure_industry_types()


def _add_custom_field():
    fieldname = "custom_industry_type"
    doctype = "Company"

    if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
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
        print(f"Custom field error: {e}")


def _ensure_industry_types():
    """Ensure required industry types exist for industry-based customizations."""
    required = ["Construction"]

    for ind in required:
        if frappe.db.exists("Industry Type", ind):
            continue
        try:
            frappe.get_doc({
                "doctype": "Industry Type",
                "industry": ind,
            }).insert(ignore_permissions=True)
            print(f"Created Industry Type: {ind}")
        except Exception as e:
            print(f"Industry Type {ind} error: {e}")

    frappe.db.commit()
