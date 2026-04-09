import frappe


def after_wizard_complete(args=None):
    """
    Runs after Setup Wizard completes, BEFORE demo data (which is enqueued).
    1. Permanently relax custom_country so demo data works
    2. Setup Saudi VAT accounts and templates
    3. If demo requested, enqueue VAT setup for Demo Company (runs after demo)
    """
    try:
        relax_custom_country()
        setup_saudi_vat()

        if args and args.get("setup_demo"):
            register_demo_company_hook()

    except Exception as e:
        frappe.log_error(f"Post-wizard setup error: {e}", "SaaS VAT Setup")


def relax_custom_country():
    """Permanently make custom_country optional."""
    cf = frappe.db.get_value(
        "Custom Field",
        {"fieldname": "custom_country", "dt": "Customer"},
        "name",
    )
    if cf:
        frappe.db.set_value("Custom Field", cf, "reqd", 0)
        frappe.db.commit()
        frappe.clear_cache()


def find_parent_account(company_name, abbr):
    """Find Duties and Taxes parent account (handles numbered charts)."""
    for c in [f"Duties and Taxes - {abbr}", f"Tax Assets - {abbr}",
              f"Current Liabilities - {abbr}"]:
        if frappe.db.exists("Account", c):
            return c

    for pattern in [f"%Duties and Taxes - {abbr}", f"%Tax Assets - {abbr}"]:
        result = frappe.db.get_value(
            "Account",
            {"name": ["like", pattern], "company": company_name, "is_group": 1},
            "name",
        )
        if result:
            return result

    return frappe.db.get_value(
        "Account",
        {"company": company_name, "is_group": 1, "root_type": "Liability"},
        "name",
    )


def create_vat_for_company(company_name, abbr):
    """Create VAT accounts, tax templates, and set cost center."""
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

    # Tax templates with ZATCA custom_tax_type for proper XML category code
    # Standard Rate -> S, Zero Rate -> Z, Except Rate -> E, Out of scope -> O
    templates = [
        ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {abbr}", f"VAT 15% - {abbr}", 15.0, 1, "Standard Rate"),
        ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {abbr}", f"VAT Zero-Rated - {abbr}", 0.0, 0, "Zero Rate"),
        ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {abbr}", f"VAT Exempted - {abbr}", 0.0, 0, "Except Rate"),
        ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {abbr}", f"VAT 15% - {abbr}", 15.0, 1, "Standard Rate"),
    ]

    for dt, title, head, rate, default, tax_type in templates:
        if not frappe.db.exists(dt, title):
            try:
                tx = {
                    "charge_type": "On Net Total",
                    "account_head": head,
                    "description": title,
                    "rate": rate,
                }
                if "Purchase" in dt:
                    tx["category"] = "Total"
                    tx["add_deduct_tax"] = "Add"
                doc = frappe.get_doc({
                    "doctype": dt,
                    "title": title,
                    "company": company_name,
                    "is_default": default,
                    "custom_tax_type": tax_type,
                    "taxes": [tx],
                })
                doc.insert(ignore_permissions=True)
            except Exception:
                pass
        else:
            # Ensure custom_tax_type is set on existing templates
            current = frappe.db.get_value(dt, title, "custom_tax_type")
            if not current:
                frappe.db.set_value(dt, title, "custom_tax_type", tax_type)

    cc = frappe.db.get_value("Cost Center", {"company": company_name, "is_group": 0}, "name")
    if cc:
        frappe.db.set_value("Company", company_name, "round_off_cost_center", cc)
        frappe.db.set_value("Company", company_name, "depreciation_cost_center", cc)

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
    """Setup VAT for all existing companies."""
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    for co in companies:
        create_vat_for_company(co.name, co.abbr)


def register_demo_company_hook():
    """Enqueue VAT setup for Demo Company (runs after demo data completes)."""
    frappe.enqueue(
        "zatca_integration.setup_wizard_hook.setup_demo_company_vat",
        queue="long",
        enqueue_after_commit=True,
        at_front=False,
        timeout=600,
    )


def setup_demo_company_vat():
    """
    Called from queue after demo data.
    Wait for Demo Company to exist, then setup VAT.
    """
    import time

    # Wait up to 5 minutes for demo data to finish creating the company
    for i in range(30):
        demo_company = frappe.db.get_single_value("Global Defaults", "demo_company")
        if demo_company and frappe.db.exists("Company", demo_company):
            break
        time.sleep(10)
    else:
        return

    abbr = frappe.db.get_value("Company", demo_company, "abbr")
    create_vat_for_company(demo_company, abbr)

    # Fix customers without country
    customers = frappe.get_all(
        "Customer",
        filters={"custom_country": ["in", ["", None]]},
        pluck="name",
    )
    for c in customers:
        frappe.db.set_value("Customer", c, "custom_country", "Saudi Arabia")

    if customers:
        frappe.db.commit()
