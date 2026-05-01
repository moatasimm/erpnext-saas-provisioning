import frappe

def execute():
    item_name = "Retention Release"
    if frappe.db.exists("Item", item_name):
        deps = frappe.db.sql(
            "SELECT parent FROM `tabSales Invoice Item` WHERE item_code=%s LIMIT 5",
            item_name, as_dict=True
        )
        print(f"SI line items referencing this item: {[d.parent for d in deps]}")
        frappe.delete_doc("Item", item_name, ignore_permissions=True, force=True)
        frappe.db.commit()
        print(f"✓ Deleted Item '{item_name}'")
    else:
        print(f"Item '{item_name}' not found — nothing to delete.")
