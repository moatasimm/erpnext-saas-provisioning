"""
fix_zatca_links.py — Links companies to existing Zatca CSR Settings and Production CSID.
Run via: bench --site <site> execute frappe.utils._fix_zatca_links.run
"""
import frappe


def run():
    try:
        csr_list = frappe.get_all("Zatca CSR Settings", limit=1, pluck="name")
        prod_list = frappe.get_all("Production CSID", limit=1, pluck="name")

        csr_name = csr_list[0] if csr_list else None
        prod_name = prod_list[0] if prod_list else None

        if not csr_name and not prod_name:
            print("  No Zatca CSR Settings or Production CSID found. Skipping.")
            return

        for co in frappe.get_all("Company", pluck="name"):
            if csr_name and not frappe.db.get_value("Company", co, "custom_csr_settings"):
                frappe.db.set_value("Company", co, "custom_csr_settings", csr_name)
                print(f"  {co}: custom_csr_settings -> {csr_name}")

            if prod_name and not frappe.db.get_value("Company", co, "custom_production_csid"):
                frappe.db.set_value("Company", co, "custom_production_csid", prod_name)
                print(f"  {co}: custom_production_csid -> {prod_name}")

        frappe.db.commit()
        print("  Done.")
    except Exception as e:
        print(f"  Error: {e}")
        frappe.log_error(f"fix_zatca_links error: {e}", "Opentra SaaS")
