import frappe


def after_wizard_complete(args=None):
    """
    Runs after Setup Wizard completes, BEFORE demo data (which is enqueued).
    1. Relax custom_country so demo data doesn't fail
    2. Setup Saudi VAT accounts and templates
    3. If demo was requested, prepare Demo Company VAT + cost center
    """
    try:
        # Step 1: Relax custom_country mandatory (ZATCA adds it on Customer)
        # This MUST happen before demo data runs in the background queue
        relax_custom_country()

        # Step 2: Setup VAT for the main company
        setup_saudi_vat()

        # Step 3: If demo data was requested, hook into demo company creation
        # The demo runs via frappe.enqueue (background), so we register
        # a doc_event hook to catch when Demo Company is created
        if args and args.get("setup_demo"):
            register_demo_company_hook()

    except Exception as e:
        frappe.log_error(f"Post-wizard setup error: {e}", "SaaS VAT Setup")
        print(f"Setup error: {e}")


def relax_custom_country():
    """Make custom_country not mandatory so demo data can create Customers."""
    cf = frappe.db.get_value(
        "Custom Field",
        {"fieldname": "custom_country", "dt": "Customer"},
        "name",
    )
    if cf:
        frappe.db.set_value("Custom Field", cf, "reqd", 0)
        frappe.db.commit()
        frappe.clear_cache()
        print("custom_country relaxed for demo data")


def find_parent_account(company_name, abbr):
    """Find Duties and Taxes parent account (handles numbered charts)."""
    # Try exact match first
    for c in [f"Duties and Taxes - {abbr}", f"Tax Assets - {abbr}",
              f"Current Liabilities - {abbr}"]:
        if frappe.db.exists("Account", c):
            return c

    # Search with LIKE for numbered charts (e.g. "2300 - Duties and Taxes - DC")
    for pattern in [f"%Duties and Taxes - {abbr}", f"%Tax Assets - {abbr}"]:
        result = frappe.db.get_value(
            "Account",
            {"name": ["like", pattern], "company": company_name, "is_group": 1},
            "name",
        )
        if result:
            return result

    # Fallback
    return frappe.db.get_value(
        "Account",
        {"company": company_name, "is_group": 1, "root_type": "Liability"},
        "name",
    )


def create_vat_for_company(company_name, abbr):
    """Create VAT accounts and tax templates for a company."""
    pa = find_parent_account(company_name, abbr)
    if not pa:
        print(f"  No parent account for {company_name}")
        return

    print(f"  VAT parent: {pa}")

    # Create VAT accounts
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
            # Fix parent if wrong
            current = frappe.db.get_value("Account", full_name, "parent_account")
            if current != pa:
                frappe.db.set_value("Account", full_name, "parent_account", pa)

    # Create tax templates
    templates = [
        ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {abbr}", f"VAT 15% - {abbr}", 15.0, 1),
        ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {abbr}", f"VAT Zero-Rated - {abbr}", 0.0, 0),
        ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {abbr}", f"VAT Exempted - {abbr}", 0.0, 0),
        ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {abbr}", f"VAT 15% - {abbr}", 15.0, 1),
    ]

    for dt, title, head, rate, default in templates:
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
                frappe.get_doc({
                    "doctype": dt,
                    "title": title,
                    "company": company_name,
                    "is_default": default,
                    "taxes": [tx],
                }).insert(ignore_permissions=True)
            except Exception:
                pass

    # Set round_off_cost_center
    cc = frappe.db.get_value("Cost Center", {"company": company_name, "is_group": 0}, "name")
    if cc:
        frappe.db.set_value("Company", company_name, "round_off_cost_center", cc)
        frappe.db.set_value("Company", company_name, "depreciation_cost_center", cc)

    # ZATCA Settings
    try:
        if frappe.db.exists("DocType", "ZATCA Setting"):
            z = frappe.get_single("ZATCA Setting")
            if not z.company:
                z.company = company_name
                z.save(ignore_permissions=True)
    except Exception:
        pass

    frappe.db.commit()
    print(f"  VAT setup complete for {company_name}")


def setup_saudi_vat():
    """Setup VAT for all existing companies."""
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    for co in companies:
        print(f"VAT setup: {co.name} ({co.abbr})")
        create_vat_for_company(co.name, co.abbr)
    print("Saudi VAT auto-setup complete!")


def register_demo_company_hook():
    """
    Register a hook so when Demo Company is created by ERPNext demo,
    we automatically add VAT accounts and templates to it.
    """
    # We use doc_events to catch new Company creation
    # But since doc_events need to be in hooks.py, we use a simpler approach:
    # Schedule a delayed task to setup VAT for any new companies
    frappe.enqueue(
        "zatca_integration.setup_wizard_hook.setup_demo_company_vat",
        queue="long",
        enqueue_after_commit=True,
        at_front=False,  # Run AFTER demo data completes
    )
    print("Demo company VAT hook registered")


def setup_demo_company_vat():
    """
    Called from queue after demo data finishes.
    Finds the Demo Company and sets up VAT for it.
    Also fixes customers without custom_country.
    """
    try:
        demo_company = frappe.db.get_single_value("Global Defaults", "demo_company")
        if demo_company and frappe.db.exists("Company", demo_company):
            abbr = frappe.db.get_value("Company", demo_company, "abbr")
            print(f"Setting up VAT for demo company: {demo_company} ({abbr})")
            create_vat_for_company(demo_company, abbr)

        # Fix customers without custom_country
        customers = frappe.get_all(
            "Customer",
            filters={"custom_country": ["in", ["", None]]},
            pluck="name",
        )
        for c in customers:
            frappe.db.set_value("Customer", c, "custom_country", "Saudi Arabia")

        if customers:
            frappe.db.commit()
            print(f"Fixed {len(customers)} customers without country")

        # Restore custom_country as mandatory
        cf = frappe.db.get_value(
            "Custom Field",
            {"fieldname": "custom_country", "dt": "Customer"},
            "name",
        )
        if cf:
            frappe.db.set_value("Custom Field", cf, "reqd", 1)
            frappe.db.commit()
            print("custom_country restored to mandatory")

    except Exception as e:
        frappe.log_error(f"Demo company VAT setup error: {e}", "SaaS VAT Setup")
