import frappe


def after_wizard_complete(args=None):
    """Auto-setup Saudi VAT after Setup Wizard completes."""
    try:
        setup_saudi_vat()
    except Exception as e:
        frappe.log_error(f"Auto VAT setup error: {e}", "SaaS VAT Setup")
        print(f"VAT setup error: {e}")


def find_parent_account(company_name, abbr):
    """Find the correct Duties and Taxes parent account.
    Handles both numbered (2300 - Duties and Taxes - DC)
    and standard (Duties and Taxes - DC) chart of accounts.
    """
    # Try exact matches first
    candidates = [
        f"Duties and Taxes - {abbr}",
        f"Tax Assets - {abbr}",
    ]
    for c in candidates:
        if frappe.db.exists("Account", c):
            return c

    # Search with LIKE for numbered charts (e.g. "2300 - Duties and Taxes - DC")
    like_candidates = [
        f"%Duties and Taxes - {abbr}",
        f"%Tax Assets - {abbr}",
    ]
    for pattern in like_candidates:
        result = frappe.db.get_value(
            "Account",
            {"name": ["like", pattern], "company": company_name, "is_group": 1},
            "name",
        )
        if result:
            return result

    # Fallback: any Liability group account
    result = frappe.db.get_value(
        "Account",
        {"company": company_name, "is_group": 1, "root_type": "Liability"},
        "name",
    )
    return result


def setup_saudi_vat():
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    if not companies:
        return

    for co in companies:
        cn = co.name
        ab = co.abbr

        pa = find_parent_account(cn, ab)
        if not pa:
            print(f"No parent account found for {cn}, skipping")
            continue

        print(f"VAT setup for {cn} ({ab}), parent: {pa}")

        # Create VAT accounts
        for an, r in [("VAT 15%", 15.0), ("VAT Zero-Rated", 0.0), ("VAT Exempted", 0.0)]:
            full_name = f"{an} - {ab}"
            if not frappe.db.exists("Account", full_name):
                try:
                    frappe.get_doc({
                        "doctype": "Account",
                        "account_name": an,
                        "parent_account": pa,
                        "company": cn,
                        "account_type": "Tax",
                        "tax_rate": r,
                        "is_group": 0,
                    }).insert(ignore_permissions=True)
                    print(f"  + {an}")
                except Exception as e:
                    print(f"  ! {an}: {e}")
            else:
                # Fix parent if account exists under wrong parent
                current_parent = frappe.db.get_value("Account", full_name, "parent_account")
                if current_parent != pa:
                    frappe.db.set_value("Account", full_name, "parent_account", pa)
                    print(f"  ~ {an} moved to {pa}")
                else:
                    print(f"  = {an} exists")

        # Create tax templates
        tmpl_list = [
            ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {ab}", f"VAT 15% - {ab}", 15.0, 1),
            ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {ab}", f"VAT Zero-Rated - {ab}", 0.0, 0),
            ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {ab}", f"VAT Exempted - {ab}", 0.0, 0),
            ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {ab}", f"VAT 15% - {ab}", 15.0, 1),
        ]

        for dt, ti, hd, rt, df in tmpl_list:
            if not frappe.db.exists(dt, ti):
                try:
                    tx = {
                        "charge_type": "On Net Total",
                        "account_head": hd,
                        "description": ti,
                        "rate": rt,
                    }
                    if "Purchase" in dt:
                        tx["category"] = "Total"
                        tx["add_deduct_tax"] = "Add"
                    frappe.get_doc({
                        "doctype": dt,
                        "title": ti,
                        "company": cn,
                        "is_default": df,
                        "taxes": [tx],
                    }).insert(ignore_permissions=True)
                    print(f"  + {ti}")
                except Exception as e:
                    print(f"  ! {ti}: {e}")
            else:
                print(f"  = {ti} exists")

        # ZATCA Settings
        try:
            if frappe.db.exists("DocType", "ZATCA Setting"):
                z = frappe.get_single("ZATCA Setting")
                if not z.company:
                    z.company = cn
                    z.save(ignore_permissions=True)
                    print(f"  + ZATCA -> {cn}")
        except Exception as e:
            print(f"  ! ZATCA: {e}")

        frappe.db.commit()

    print("Saudi VAT auto-setup complete!")
