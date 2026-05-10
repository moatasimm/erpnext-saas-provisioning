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
from frappe.utils import flt


def on_submit(doc, method=None):
    if not doc.get("custom_retention_release"):
        return
    try:
        release = frappe.get_doc("Retention Release", doc.custom_retention_release)
        if release.docstatus != 1 or release.status != "Submitted":
            return

        paid_amount = flt(doc.paid_amount)
        release_amount = flt(release.release_amount)

        if paid_amount < release_amount:
            frappe.throw(
                f"المبلغ المدفوع ({paid_amount:,.2f}) أقل من مبلغ الإفراج عن الضمان ({release_amount:,.2f}).\n\n"
                f"يجب دفع المبلغ كاملاً دفعةً واحدة.\n\n"
                f"إذا كنت ترغب في دفع مبلغ جزئي، يُرجى إنشاء سند إفراج عن ضمان (Retention Release) "
                f"بالمبلغ الجزئي المطلوب ({paid_amount:,.2f}) ثم دفعه كاملاً.\n\n"
                f"Payment amount ({paid_amount:,.2f}) is less than the retention release amount ({release_amount:,.2f}).\n"
                f"Payment must be made in full in a single payment.\n"
                f"To pay a partial amount, please create a new Retention Release for the partial amount "
                f"({paid_amount:,.2f}) and pay it in full.",
                title="خطأ في مبلغ الدفع / Payment Amount Error",
            )

        if paid_amount > release_amount:
            frappe.throw(
                f"المبلغ المدفوع ({paid_amount:,.2f}) أكبر من مبلغ الإفراج عن الضمان ({release_amount:,.2f}).\n\n"
                f"يجب أن يساوي المبلغ المدفوع مبلغ الإفراج عن الضمان تماماً.\n\n"
                f"Payment amount ({paid_amount:,.2f}) exceeds the retention release amount ({release_amount:,.2f}).\n"
                f"Payment must equal the retention release amount exactly.",
                title="خطأ في مبلغ الدفع / Payment Amount Error",
            )

        frappe.db.set_value("Retention Release", release.name, "status", "Paid")
        frappe.msgprint(
            f"تم تسجيل دفع الضمان بنجاح بمبلغ {release_amount:,.2f} SAR",
            indicator="green",
            alert=True,
        )
    except frappe.ValidationError:
        raise
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
