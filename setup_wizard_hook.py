import frappe
import re


def after_wizard_complete(args=None):
    """Runs after Setup Wizard completes."""
    try:
        apply_industry_from_config()
        relax_custom_country()
        fix_retention_account_filter()
        setup_saudi_vat()
        create_custom_zatca_print_format()

        if args and args.get("setup_demo"):
            register_demo_company_hook()
    except Exception as e:
        frappe.log_error(f"Post-wizard setup error: {e}", "SaaS VAT Setup")


def apply_industry_from_config():
    """Read custom_industry_type from site_config.json and apply to all companies."""
    try:
        industry = frappe.local.conf.get("custom_industry_type")
        if not industry:
            return
        for co in frappe.get_all("Company", pluck="name"):
            try:
                frappe.db.set_value("Company", co, "custom_industry_type", industry)
            except Exception:
                pass
        frappe.db.commit()
    except Exception:
        pass


def relax_custom_country():
    cf = frappe.db.get_value(
        "Custom Field",
        {"fieldname": "custom_country", "dt": "Customer"},
        "name",
    )
    if cf:
        frappe.db.set_value("Custom Field", cf, "reqd", 0)
        frappe.db.commit()
        frappe.clear_cache()
def fix_retention_account_filter():
    """Fix ZATCA's incorrect link filter on custom_retention_account (Receivable -> Payable)."""
    try:
        cf_name = "Sales Invoice-custom_retention_account"
        if frappe.db.exists("Custom Field", cf_name):
            correct_filter = '[["Account","account_type","=","Payable"]]'
            current = frappe.db.get_value("Custom Field", cf_name, "link_filters")
            if current != correct_filter:
                frappe.db.set_value("Custom Field", cf_name, "link_filters", correct_filter)
                frappe.db.commit()
                frappe.clear_cache()
    except Exception:
        pass

def find_parent_account(company_name, abbr):
    for c in [f"Duties and Taxes - {abbr}", f"Tax Assets - {abbr}",
              f"Current Liabilities - {abbr}"]:
        if frappe.db.exists("Account", c):
            return c
    for pattern in [f"%Duties and Taxes - {abbr}", f"%Tax Assets - {abbr}"]:
        result = frappe.db.get_value("Account",
            {"name": ["like", pattern], "company": company_name, "is_group": 1}, "name")
        if result:
            return result
    return frappe.db.get_value("Account",
        {"company": company_name, "is_group": 1, "root_type": "Liability"}, "name")


def enable_zatca_on_company(company_name):
    try:
        meta = frappe.get_meta("Company")
        field_names = [f.fieldname for f in meta.fields]
        if "custom_enable_zatca_e_invoicing" in field_names:
            frappe.db.set_value("Company", company_name, "custom_enable_zatca_e_invoicing", 1)
        if "custom_zatca_phase" in field_names:
            frappe.db.set_value("Company", company_name, "custom_zatca_phase", "ZATCA Phase 2")
    except Exception:
        pass


def setup_construction_features(company_name, abbr):
    """Apply Construction-specific setup: Retention account + enable retention."""
    parent = None
    for pattern in [f"%Current Liabilities - {abbr}", f"%Accounts Payable - {abbr}"]:
        parent = frappe.db.get_value("Account",
            {"name": ["like", pattern], "company": company_name, "is_group": 1}, "name")
        if parent:
            break
    if not parent:
        return

    retention_account = f"Retention Payable - {abbr}"
    if not frappe.db.exists("Account", retention_account):
        try:
            frappe.get_doc({
                "doctype": "Account",
                "account_name": "Retention Payable",
                "parent_account": parent,
                "company": company_name,
                "account_type": "Payable",
                "is_group": 0,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    try:
        frappe.db.set_value("Company", company_name, "custom_enable_sales_retention", 1)
    except Exception:
        pass


def apply_industry_customizations(company_name):
    """Read custom_industry_type and apply industry-specific setup."""
    try:
        industry = frappe.db.get_value("Company", company_name, "custom_industry_type")
    except Exception:
        return

    if not industry:
        return

    abbr = frappe.db.get_value("Company", company_name, "abbr")
    if not abbr:
        return

    if industry in ("Construction", "Real Estate"):
        setup_construction_features(company_name, abbr)


def create_vat_for_company(company_name, abbr):
    pa = find_parent_account(company_name, abbr)
    if not pa:
        return

    for acc_name, rate in [("VAT 15%", 15.0), ("VAT Zero-Rated", 0.0), ("VAT Exempted", 0.0)]:
        full_name = f"{acc_name} - {abbr}"
        if not frappe.db.exists("Account", full_name):
            try:
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": acc_name,
                    "parent_account": pa,
                    "company": company_name,
                    "account_type": "Tax",
                    "tax_rate": rate,
                    "is_group": 0,
                }).insert(ignore_permissions=True)
            except Exception:
                pass
        else:
            current = frappe.db.get_value("Account", full_name, "parent_account")
            if current != pa:
                frappe.db.set_value("Account", full_name, "parent_account", pa)

    templates = [
        ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {abbr}", f"VAT 15% - {abbr}", 15.0, 1, "Standard Rate"),
        ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {abbr}", f"VAT Zero-Rated - {abbr}", 0.0, 0, "Zero Rate"),
        ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {abbr}", f"VAT Exempted - {abbr}", 0.0, 0, "Except Rate"),
        ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {abbr}", f"VAT 15% - {abbr}", 15.0, 1, "Standard Rate"),
    ]

    for dt, title, head, rate, default, tax_type in templates:
        if not frappe.db.exists(dt, title):
            try:
                tx = {"charge_type": "On Net Total", "account_head": head,
                      "description": title, "rate": rate}
                if "Purchase" in dt:
                    tx["category"] = "Total"
                    tx["add_deduct_tax"] = "Add"
                frappe.get_doc({
                    "doctype": dt, "title": title, "company": company_name,
                    "is_default": default, "custom_tax_type": tax_type, "taxes": [tx],
                }).insert(ignore_permissions=True)
            except Exception:
                pass
        else:
            if not frappe.db.get_value(dt, title, "custom_tax_type"):
                frappe.db.set_value(dt, title, "custom_tax_type", tax_type)

    cc = frappe.db.get_value("Cost Center", {"company": company_name, "is_group": 0}, "name")
    if cc:
        frappe.db.set_value("Company", company_name, "round_off_cost_center", cc)
        frappe.db.set_value("Company", company_name, "depreciation_cost_center", cc)

    enable_zatca_on_company(company_name)

    # Apply industry-specific customizations (Construction, Real Estate, etc.)
    apply_industry_customizations(company_name)

    try:
        if frappe.db.exists("DocType", "ZATCA Setting"):
            z = frappe.get_single("ZATCA Setting")
            if not z.company:
                z.company = company_name
                z.save(ignore_permissions=True)
    except Exception:
        pass

    frappe.db.commit()


def setup_saudi_vat():
    for co in frappe.get_all("Company", fields=["name", "abbr"]):
        create_vat_for_company(co.name, co.abbr)


def create_custom_zatca_print_format():
    SOURCE = "Zatca PDF-A 3B"
    CUSTOM = "Zatca PDF-A 3B Custom"
    try:
        if not frappe.db.exists("Print Format", SOURCE):
            return
        if frappe.db.exists("Print Format", CUSTOM):
            return
        source = frappe.get_doc("Print Format", SOURCE)
        html = source.html or ""
        pattern = re.compile(
            r'<!--\s*<td\s+rowspan="3"[^>]*>\s*-->\s*'
            r'<!--\s*\{%\s*if\s*doc\.get\(\'custom_invoice_qr_code\'\).*?%\}\s*-->\s*'
            r'<!--\s*<img\s+src="\{\{doc\.custom_invoice_qr_code.*?\}\}">\s*-->\s*'
            r'<!--\s*\{%\s*endif\s*%\}\s*-->\s*'
            r'<!--\s*</td>\s*-->',
            re.DOTALL
        )
        replacement = '''<td rowspan="2" style="width: 150px; text-align: center; vertical-align: middle; padding: 10px;">
{% if doc.get('custom_invoice_qr_code') %}
<img src="{{ doc.custom_invoice_qr_code }}" style="width: 130px; height: 130px;">
{% endif %}
</td>'''
        new_html = pattern.sub(replacement, html)
        empty_wrapper = re.compile(
            r'<td\s+rowspan="2">\s*<table>\s*<tr>\s*</tr>\s*</table>\s*</td>',
            re.DOTALL
        )
        new_html = empty_wrapper.sub(replacement, new_html)

        custom = frappe.new_doc("Print Format")
        custom.name = CUSTOM
        custom.doc_type = "Sales Invoice"
        custom.module = "Accounts"
        custom.standard = "No"
        custom.print_format_type = "Jinja"
        custom.html = new_html
        custom.font_size = 14
        custom.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass


def register_demo_company_hook():
    frappe.enqueue(
        "zatca_integration.setup_wizard_hook.setup_demo_company_vat",
        queue="long",
        enqueue_after_commit=True,
        at_front=False,
        timeout=600,
    )


def setup_demo_company_vat():
    import time
    for i in range(30):
        demo_company = frappe.db.get_single_value("Global Defaults", "demo_company")
        if demo_company and frappe.db.exists("Company", demo_company):
            break
        time.sleep(10)
    else:
        return

    # Apply industry from site_config to Demo Company before VAT setup
    try:
        industry = frappe.local.conf.get("custom_industry_type")
        if industry:
            frappe.db.set_value("Company", demo_company, "custom_industry_type", industry)
            frappe.db.commit()
    except Exception:
        pass

    abbr = frappe.db.get_value("Company", demo_company, "abbr")
    create_vat_for_company(demo_company, abbr)

    customers = frappe.get_all(
        "Customer",
        filters={"custom_country": ["in", ["", None]]},
        pluck="name",
    )
    for c in customers:
        frappe.db.set_value("Customer", c, "custom_country", "Saudi Arabia")
    if customers:
        frappe.db.commit()
