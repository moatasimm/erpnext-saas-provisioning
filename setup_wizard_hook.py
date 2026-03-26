import frappe


def after_wizard_complete(args=None):
    """Auto-setup Saudi VAT after Setup Wizard completes."""
    try:
        setup_saudi_vat()
    except Exception as e:
        frappe.log_error(f"Auto VAT setup error: {e}", "SaaS VAT Setup")
        print(f"VAT setup error: {e}")


def setup_saudi_vat():
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    if not companies:
        return

    for co in companies:
        cn = co.name
        ab = co.abbr

        pa = None
        for c in [f"Duties and Taxes - {ab}", f"Tax Assets - {ab}", f"Current Liabilities - {ab}"]:
            if frappe.db.exists("Account", c):
                pa = c
                break
        if not pa:
            pa = frappe.db.get_value(
                "Account",
                {"company": cn, "is_group": 1, "root_type": "Liability"},
                "name",
            )
        if not pa:
            continue

        for an, r in [("VAT 15%", 15.0), ("VAT Zero-Rated", 0.0), ("VAT Exempted", 0.0)]:
            if not frappe.db.exists("Account", f"{an} - {ab}"):
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
                except Exception:
                    pass

        for dt, ti, hd, rt, df in [
            ("Sales Taxes and Charges Template", f"Saudi VAT 15% - {ab}", f"VAT 15% - {ab}", 15.0, 1),
            ("Sales Taxes and Charges Template", f"Saudi VAT Zero - {ab}", f"VAT Zero-Rated - {ab}", 0.0, 0),
            ("Sales Taxes and Charges Template", f"Saudi VAT Exempt - {ab}", f"VAT Exempted - {ab}", 0.0, 0),
            ("Purchase Taxes and Charges Template", f"Saudi VAT 15% Purch - {ab}", f"VAT 15% - {ab}", 15.0, 1),
        ]:
            if not frappe.db.exists(dt, ti):
                try:
                    tx = {"charge_type": "On Net Total", "account_head": hd, "description": ti, "rate": rt}
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
                except Exception:
                    pass

        try:
            if frappe.db.exists("DocType", "ZATCA Setting"):
                z = frappe.get_single("ZATCA Setting")
                if not z.company:
                    z.company = cn
                    z.save(ignore_permissions=True)
        except Exception:
            pass

        frappe.db.commit()

    print("Saudi VAT auto-setup complete!")
