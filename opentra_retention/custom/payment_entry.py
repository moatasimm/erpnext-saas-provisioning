"""
Payment Entry customization for Retention.

Logic:
- on_submit: If PE has custom_retention_release set, mark that Retention Release
             as 'Paid'.
- on_cancel: If PE has custom_retention_release set, revert the Retention Release
             back to 'Submitted' so it can be paid again.

Retention Payment Entries are created via the "Create Payment Entry" button on
the Retention Release form (api.make_retention_payment_entry). They carry no
reference rows — the Retention Release is linked via custom_retention_release.
"""

import frappe


def on_submit(doc, method=None):
    if not doc.get("custom_retention_release"):
        return
    try:
        release = frappe.get_doc("Retention Release", doc.custom_retention_release)
        if release.docstatus == 1 and release.status == "Submitted":
            frappe.db.set_value("Retention Release", release.name, "status", "Paid")
    except Exception as exc:
        frappe.log_error(
            title="Retention Release — mark_paid error",
            message=f"PE {doc.name}: {exc}",
        )


def on_cancel(doc, method=None):
    if not doc.get("custom_retention_release"):
        return
    try:
        release = frappe.get_doc("Retention Release", doc.custom_retention_release)
        if release.docstatus == 1 and release.status == "Paid":
            frappe.db.set_value("Retention Release", release.name, "status", "Submitted")

        # Cancel the Payment Transfer JV (DR Debtors | CR 1312) that was created
        # when this PE was built. Without this the SI outstanding is left inflated.
        jv_name = frappe.db.get_value(
            "Retention Release", release.name, "payment_transfer_jv"
        )
        if jv_name and frappe.db.exists("Journal Entry", jv_name):
            if frappe.db.get_value("Journal Entry", jv_name, "docstatus") == 1:
                jv_doc = frappe.get_doc("Journal Entry", jv_name)
                jv_doc.flags.ignore_links = True
                jv_doc.cancel()
                frappe.db.set_value(
                    "Retention Release", release.name, "payment_transfer_jv", None
                )
    except Exception as exc:
        frappe.log_error(
            title="Retention Release — revert on cancel error",
            message=f"PE {doc.name}: {exc}",
        )
