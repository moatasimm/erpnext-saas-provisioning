#!/usr/bin/env python3
"""
Create 'Zatca PDF-A 3B Custom' print format on a site.
Copies the standard 'Zatca PDF-A 3B' format and uncomments the QR code block.

Usage:
    bench --site SITENAME execute frappe.utils._zatca_pf_setup.run

This script is meant to be installed via install_hook.sh into:
    /home/frappe/frappe-bench/apps/frappe/frappe/utils/_zatca_pf_setup.py
"""

import re

import frappe


CUSTOM_NAME = "Zatca PDF-A 3B Custom"
SOURCE_NAME = "Zatca PDF-A 3B"

# Pattern to find the commented QR block
COMMENTED_QR_PATTERN = re.compile(
    r'<!--\s*<td\s+rowspan="3"[^>]*>\s*-->\s*'
    r'<!--\s*\{%\s*if\s*doc\.get\(\'custom_invoice_qr_code\'\).*?%\}\s*-->\s*'
    r'<!--\s*<img\s+src="\{\{doc\.custom_invoice_qr_code.*?\}\}">\s*-->\s*'
    r'<!--\s*\{%\s*endif\s*%\}\s*-->\s*'
    r'<!--\s*</td>\s*-->',
    re.DOTALL
)

QR_REPLACEMENT = '''<td rowspan="2" style="width: 150px; text-align: center; vertical-align: middle; padding: 10px;">
{% if doc.get('custom_invoice_qr_code') %}
<img src="{{ doc.custom_invoice_qr_code }}" style="width: 130px; height: 130px;">
{% endif %}
</td>'''


def run():
    """Create or update Zatca PDF-A 3B Custom print format with QR enabled."""
    if not frappe.db.exists("Print Format", SOURCE_NAME):
        print(f"Source format '{SOURCE_NAME}' not found, skipping")
        return

    source = frappe.get_doc("Print Format", SOURCE_NAME)
    original_html = source.html

    # Try to uncomment the QR block via regex
    if COMMENTED_QR_PATTERN.search(original_html):
        new_html = COMMENTED_QR_PATTERN.sub(QR_REPLACEMENT, original_html)
        print("QR block uncommented via regex")
    else:
        # Fallback: also handle the empty <td rowspan="2"> case
        empty_td_pattern = re.compile(
            r'<td\s+rowspan="2">\s*<table>\s*<tr>\s*'
            r'(?:<!--[^>]*-->\s*)*'
            r'</tr>\s*</table>\s*</td>',
            re.DOTALL
        )
        if empty_td_pattern.search(original_html):
            new_html = empty_td_pattern.sub(QR_REPLACEMENT, original_html)
            print("Empty QR td replaced")
        else:
            print("WARNING: Could not find QR placeholder. Custom format will be identical to source.")
            new_html = original_html

    # Create or update the custom format
    if frappe.db.exists("Print Format", CUSTOM_NAME):
        custom = frappe.get_doc("Print Format", CUSTOM_NAME)
        custom.html = new_html
        custom.save(ignore_permissions=True)
        print(f"Updated existing: {CUSTOM_NAME}")
    else:
        custom = frappe.new_doc("Print Format")
        custom.name = CUSTOM_NAME
        custom.doc_type = "Sales Invoice"
        custom.module = "Accounts"
        custom.standard = "No"
        custom.print_format_type = "Jinja"
        custom.html = new_html
        custom.font_size = 14
        custom.margin_top = 15.0
        custom.margin_bottom = 15.0
        custom.margin_left = 15.0
        custom.margin_right = 15.0
        custom.insert(ignore_permissions=True)
        print(f"Created: {CUSTOM_NAME}")

    frappe.db.commit()
    print("Done!")
