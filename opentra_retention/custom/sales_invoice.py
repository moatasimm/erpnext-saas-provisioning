"""
Sales Invoice customization for Retention.

Logic:
- validate:   Calculate retention_amount (auto from %) + net_after_retention
- on_submit:  If retention_amount > 0 → create Journal Entry:
                  DR  Retention Receivable   = retention_amount
                  CR  AR (debit_to)          = retention_amount
              Net effect: AR outstanding = grand_total - retention_amount
- on_cancel:  Cancel the companion JV
"""

import frappe
from frappe import _
from frappe.utils import flt


# ──────────────────────────────────────────────────────────────────────────────
#  validate
# ──────────────────────────────────────────────────────────────────────────────

def validate(doc, method=None):
    """Auto-calculate retention amount & net_after_retention."""
    grand_total = flt(doc.grand_total)
    net_total   = flt(doc.net_total)

    if doc.custom_retention_percentage:
        # Auto mode: calculate from percentage of net_total
        rate = float(str(doc.custom_retention_percentage).replace("%", "").strip()) / 100.0
        doc.custom_retention_amount = flt(net_total * rate, doc.precision("grand_total"))
    # else: manual mode — keep whatever the user entered

    retention = flt(doc.custom_retention_amount)
    doc.custom_net_after_retention = flt(grand_total - retention, doc.precision("grand_total"))


# ──────────────────────────────────────────────────────────────────────────────
#  on_submit
# ──────────────────────────────────────────────────────────────────────────────

def on_submit(doc, method=None):
    """Create retention Journal Entry after invoice is submitted."""
    retention_amount = flt(doc.custom_retention_amount)
    if retention_amount <= 0:
        return

    retention_account = _get_retention_account(doc.company)
    if not retention_account:
        frappe.msgprint(
            _(
                "⚠️ Retention Journal Entry NOT created — no Default Retention Receivable Account "
                "set on company <b>{0}</b>.<br>Go to Company → Accounts tab to configure it."
            ).format(doc.company),
            title=_("Retention: Missing Account"),
            indicator="orange",
        )
        return

    ar_account = doc.debit_to   # Sales Invoice always has debit_to filled
    if not ar_account:
        frappe.log_error(f"No debit_to on {doc.name}", "Retention JV: No AR Account")
        return

    jv = _create_retention_jv(doc, retention_amount, retention_account, ar_account)
    if jv:
        # Store JV reference without triggering full document save
        frappe.db.set_value("Sales Invoice", doc.name, "custom_retention_jv", jv.name)
        frappe.msgprint(
            _(
                "✅ Retention JV <b>{0}</b> created.<br>"
                "AR outstanding = {1:,.2f} | Retention Receivable = {2:,.2f}"
            ).format(
                jv.name,
                flt(doc.grand_total) - retention_amount,
                retention_amount,
            ),
            title=_("Retention Applied"),
            indicator="green",
        )


# ──────────────────────────────────────────────────────────────────────────────
#  on_cancel
# ──────────────────────────────────────────────────────────────────────────────

def on_cancel(doc, method=None):
    """Cancel the retention JV when the invoice is cancelled."""
    jv_name = doc.custom_retention_jv
    if not jv_name:
        return
    if not frappe.db.exists("Journal Entry", jv_name):
        return

    docstatus = frappe.db.get_value("Journal Entry", jv_name, "docstatus")
    if docstatus == 1:  # submitted
        try:
            jv_doc = frappe.get_doc("Journal Entry", jv_name)
            jv_doc.flags.ignore_links = True
            jv_doc.cancel()
            frappe.msgprint(
                _("Retention JV <b>{0}</b> cancelled.").format(jv_name),
                alert=True,
            )
        except Exception as exc:
            frappe.log_error(
                f"Could not cancel retention JV {jv_name} for {doc.name}: {exc}",
                "Retention Cancel Error",
            )


# ──────────────────────────────────────────────────────────────────────────────
#  helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_retention_account(company):
    return frappe.db.get_value("Company", company, "default_retention_account")


def _create_retention_jv(doc, retention_amount, retention_account, ar_account):
    """
    Journal Entry:
        DR  retention_account  (Retention Receivable)  = retention_amount
        CR  ar_account         (Debtors / AR)          = retention_amount

    This reduces the open AR for the invoice and parks the retention separately.
    """
    try:
        cost_center = frappe.db.get_value("Company", doc.company, "cost_center") or ""
        project     = doc.project or ""

        jv = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "company": doc.company,
                "posting_date": doc.posting_date,
                "user_remark": _(
                    "Retention deduction — Sales Invoice {0} — Customer {1}"
                ).format(doc.name, doc.customer),
                "accounts": [
                    # ── DR: Retention Receivable ──────────────────────────
                    # NOTE: reference_type/name are intentionally omitted — ERPNext
                    # validates that any JV row referencing a Sales Invoice must use
                    # the same account as the invoice's debit_to; Retention
                    # Receivable ≠ debit_to.  against_voucher is patched via SQL
                    # after submit so GL reports can filter by SI.
                    {
                        "account": retention_account,
                        "party_type": "Customer",
                        "party": doc.customer,
                        "debit_in_account_currency": retention_amount,
                        "credit_in_account_currency": 0.0,
                        "cost_center": cost_center,
                        "project": project,
                    },
                    # ── CR: AR (debit_to) ─────────────────────────────────
                    # Reference to the Sales Invoice reduces its outstanding amount.
                    {
                        "account": ar_account,
                        "party_type": "Customer",
                        "party": doc.customer,
                        "debit_in_account_currency": 0.0,
                        "credit_in_account_currency": retention_amount,
                        "reference_type": "Sales Invoice",
                        "reference_name": doc.name,
                        "cost_center": cost_center,
                        "project": project,
                    },
                ],
            }
        )
        jv.flags.ignore_permissions = True
        jv.insert(ignore_permissions=True)
        jv.submit()

        # The Retention Receivable leg cannot carry reference_type="Sales Invoice"
        # (ERPNext account validation), so its GL Entry gets against_voucher=NULL.
        # Patch it directly so GL reports can filter by Against Voucher = SI.
        frappe.db.sql(
            """UPDATE `tabGL Entry`
               SET against_voucher_type = 'Sales Invoice', against_voucher = %s
               WHERE voucher_no = %s AND account = %s AND is_cancelled = 0""",
            (doc.name, jv.name, retention_account),
        )

        return jv

    except Exception as exc:
        try:
            frappe.log_error(
                title="Retention JV Error",
                message=f"Invoice: {doc.name}\nError: {exc}",
            )
        except Exception:
            pass  # Never let log_error crash the whole flow
        frappe.msgprint(
            _("❌ Could not create Retention JV: {0}").format(str(exc)[:200]),
            title=_("Retention Error"),
            indicator="red",
        )
        return None
