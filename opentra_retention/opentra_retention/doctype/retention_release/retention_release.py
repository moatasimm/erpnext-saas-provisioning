# Copyright (c) 2026, Opentech and contributors
# For license information, please see license.txt
"""
Retention Release — formally releases retention from Retention Receivable back to AR.

Workflow:
  1. User creates Retention Release linked to a Sales Invoice that has retention.
  2. On Submit: a Release JV is created:
       DR  Debtors (AR)          = release_amount   [reference_type: Sales Invoice]
       CR  Retention Receivable  = release_amount
     The DR reference causes ERPNext to add release_amount back to the SI outstanding,
     so a standard Payment Entry can reference the Sales Invoice to collect it.
  3. User creates a Payment Entry referencing the Sales Invoice.
     On PE submit the on_submit hook marks this Retention Release as Paid.
  4. On Cancel: the Release JV is cancelled, reversing the AR restoration.

Balance Fields (computed on validate, read-only):
  • retention_amount          — total retention from the original invoice
  • total_already_released    — sum of other submitted releases for this invoice
  • remaining_before_release  — retention_amount − total_already_released
  • release_amount            — this document's release (user-editable)
  • remaining_after_release   — remaining_before_release − release_amount
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class RetentionRelease(Document):

    # ──────────────────────────────────────────────────────────────────────────
    #  validate
    # ──────────────────────────────────────────────────────────────────────────

    def validate(self):
        self._validate_invoice()
        self._compute_balance_fields()
        self._validate_release_amount()

    def _validate_invoice(self):
        if not self.sales_invoice:
            return
        inv = frappe.db.get_value(
            "Sales Invoice",
            self.sales_invoice,
            [
                "docstatus",
                "custom_retention_amount",
                "custom_retention_percentage",
                "customer",
                "company",
                "due_date",
            ],
            as_dict=True,
        )
        if not inv:
            frappe.throw(_("Sales Invoice {0} not found.").format(self.sales_invoice))
        if inv.docstatus != 1:
            frappe.throw(
                _("Sales Invoice <b>{0}</b> must be Submitted before releasing retention.").format(
                    self.sales_invoice
                )
            )
        if not flt(inv.custom_retention_amount):
            frappe.throw(
                _("Sales Invoice <b>{0}</b> has no retention amount set.").format(
                    self.sales_invoice
                )
            )

        # Auto-fill fields from invoice
        self.retention_amount = flt(inv.custom_retention_amount)

        if not self.customer:
            self.customer = inv.customer
        if not self.company:
            self.company = frappe.db.get_value("Sales Invoice", self.sales_invoice, "company")

        # Auto-fill retention_percentage (read-only display field)
        if not self.retention_percentage and inv.custom_retention_percentage:
            self.retention_percentage = inv.custom_retention_percentage

        # Auto-fill due_date from invoice if not set
        if not self.due_date and inv.due_date:
            self.due_date = inv.due_date

    def _compute_balance_fields(self):
        """Populate the three read-only balance/tracking fields."""
        retention_total   = flt(self.retention_amount)
        already_released  = self._get_already_released()

        self.total_already_released   = already_released
        self.remaining_before_release = flt(retention_total - already_released)
        self.remaining_after_release  = flt(
            self.remaining_before_release - flt(self.release_amount)
        )

    def _validate_release_amount(self):
        # If release_amount is empty/zero, let Frappe's reqd-field validation
        # handle it on the client side.  Do NOT throw here — it would block
        # the form before the user has had a chance to fill the field.
        if not flt(self.release_amount):
            return

        # Re-compute outstanding fresh from DB so the check is always accurate,
        # regardless of the order in which validate() methods were called.
        already_released = self._get_already_released()
        outstanding = flt(self.retention_amount) - already_released

        if flt(self.release_amount) > flt(outstanding):
            frappe.throw(
                _(
                    "Release Amount ({0:,.2f}) exceeds outstanding retention ({1:,.2f}). "
                    "Already released: {2:,.2f}."
                ).format(
                    flt(self.release_amount),
                    outstanding,
                    already_released,
                )
            )

    def _get_already_released(self):
        """Sum of release_amount from submitted Retention Release docs for this invoice (excluding self)."""
        filters = {
            "sales_invoice": self.sales_invoice,
            "docstatus": 1,
        }
        if not self.is_new() and self.name:
            filters["name"] = ["!=", self.name]

        rows = frappe.get_all(
            "Retention Release",
            filters=filters,
            fields=["sum(release_amount) as total"],
        )
        return flt(rows[0].total) if rows else 0.0

    # ──────────────────────────────────────────────────────────────────────────
    #  on_submit
    # ──────────────────────────────────────────────────────────────────────────

    def on_submit(self):
        self.db_set("status", "Submitted")
        self._create_release_jv()

    def _create_release_jv(self):
        """
        Transfer JV: moves release_amount from 1311 Retention Receivable
        to 1312 Retention Released Receivable.

        DR  1312 Retention Released Receivable  = release_amount
        CR  1311 Retention Receivable            = release_amount

        SI outstanding is NOT affected here. It is restored later (inside
        make_retention_payment_entry) when a Payment Entry is created.
        """
        retention_account = frappe.db.get_value(
            "Company", self.company, "default_retention_account"
        )
        if not retention_account:
            frappe.throw(
                _(
                    "No Default Retention Receivable Account configured for company <b>{0}</b>.<br>"
                    "Go to Company → Retention Settings to set it."
                ).format(self.company)
            )

        retention_released_account = frappe.db.get_value(
            "Company", self.company, "default_retention_released_account"
        )
        if not retention_released_account:
            frappe.throw(
                _(
                    "No Default Retention Released Account configured for company <b>{0}</b>.<br>"
                    "Go to Company → Retention Settings to set it."
                ).format(self.company)
            )

        cost_center = frappe.db.get_value("Company", self.company, "cost_center") or ""
        project     = frappe.db.get_value("Sales Invoice", self.sales_invoice, "project") or ""

        jv = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": self.company,
            "posting_date": self.release_date,
            "user_remark": _(
                "Retention Release {0} — Invoice {1} — Customer {2}"
            ).format(self.name, self.sales_invoice, self.customer),
            "accounts": [
                # DR 1312 Retention Released Receivable — approved for payment
                {
                    "account": retention_released_account,
                    "party_type": "Customer",
                    "party": self.customer,
                    "debit_in_account_currency": flt(self.release_amount),
                    "credit_in_account_currency": 0.0,
                    "cost_center": cost_center,
                    "project": project,
                },
                # CR 1311 Retention Receivable — reduces the held balance
                {
                    "account": retention_account,
                    "party_type": "Customer",
                    "party": self.customer,
                    "debit_in_account_currency": 0.0,
                    "credit_in_account_currency": flt(self.release_amount),
                    "cost_center": cost_center,
                    "project": project,
                },
            ],
        })
        jv.flags.ignore_permissions = True
        jv.insert(ignore_permissions=True)
        jv.submit()

        # Neither row can carry reference_type="Sales Invoice" (ERPNext requires the
        # account to match the SI's debit_to for that). Patch both GL rows so GL
        # reports can filter by against_voucher = Sales Invoice.
        frappe.db.sql(
            """UPDATE `tabGL Entry`
               SET against_voucher_type = 'Sales Invoice', against_voucher = %s
               WHERE voucher_no = %s AND is_cancelled = 0""",
            (self.sales_invoice, jv.name),
        )

        self.db_set("release_jv", jv.name)

        frappe.msgprint(
            _(
                "✅ Release JV <b>{0}</b> created.<br>"
                "Retention moved: 1311 Retention Receivable → 1312 Retention Released.<br>"
                "Click <b>Create Payment Entry</b> to collect this amount."
            ).format(jv.name),
            title=_("Retention Released"),
            indicator="green",
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  on_cancel
    # ──────────────────────────────────────────────────────────────────────────

    def on_cancel(self):
        self._cancel_jv("payment_transfer_jv", "Payment Transfer JV")
        self._cancel_jv("release_jv", "Release JV")
        self.db_set("status", "Cancelled")

    def _cancel_jv(self, fieldname, label):
        jv_name = frappe.db.get_value("Retention Release", self.name, fieldname)
        if not jv_name:
            return
        if not frappe.db.exists("Journal Entry", jv_name):
            return

        docstatus = frappe.db.get_value("Journal Entry", jv_name, "docstatus")
        if docstatus == 1:
            try:
                jv_doc = frappe.get_doc("Journal Entry", jv_name)
                jv_doc.flags.ignore_links = True
                jv_doc.cancel()
                frappe.msgprint(
                    _("{0} <b>{1}</b> cancelled.").format(label, jv_name),
                    alert=True,
                )
            except Exception as exc:
                frappe.log_error(
                    title="Retention Release Cancel Error",
                    message=f"Could not cancel {label} {jv_name} for {self.name}: {exc}",
                )
                frappe.throw(
                    _("Could not cancel {0} {1}: {2}").format(label, jv_name, str(exc))
                )


