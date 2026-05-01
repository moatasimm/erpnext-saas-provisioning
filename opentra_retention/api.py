"""
Whitelisted API methods for Opentra Retention.
"""

import frappe
from frappe import _
from frappe.utils import flt, today


# ──────────────────────────────────────────────────────────────────────────────
#  Standard Response Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _success(data=None, message=None):
    return {
        "success": True,
        "data": data or {},
        "message": message or "OK",
        "error": None,
        "code": None
    }

def _error(message, code="ERROR", status_code=400):
    frappe.response["http_status_code"] = status_code
    return {
        "success": False,
        "data": None,
        "message": message,
        "error": message,
        "code": code
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Portal Authentication Helper
# ──────────────────────────────────────────────────────────────────────────────

def _get_portal_customer():
    """
    Returns the customer linked to the current API user via tenant system.
    - System Users (internal): returns None (no restriction)
    - Portal Users: returns a dict with tenant details
    - Raises PermissionError if not configured
    """
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    # Internal system users have no restriction
    user_type = frappe.db.get_value("User", user, "user_type")
    if user_type == "System User":
        return None

    # Find portal user record
    portal_user = frappe.db.get_value(
        "Customer Portal User",
        {"user": user, "is_active": 1},
        ["tenant", "portal_role"],
        as_dict=True
    )

    if not portal_user:
        frappe.throw(
            "Your account is not configured for portal access. Contact support.",
            frappe.PermissionError
        )

    # Get tenant details
    tenant = frappe.db.get_value(
        "Customer Portal Tenant",
        portal_user.tenant,
        ["customer", "company", "is_active", "enable_retention"],
        as_dict=True
    )

    if not tenant or not tenant.is_active:
        frappe.throw(
            "Your tenant account is inactive. Contact support.",
            frappe.PermissionError
        )

    return {
        "customer": tenant.customer,
        "company": tenant.company,
        "tenant": portal_user.tenant,
        "portal_role": portal_user.portal_role,
        "enable_retention": tenant.enable_retention,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  get_my_profile
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_my_profile():
    try:
        user = frappe.session.user
        if user == "Guest":
            return _error("Authentication required", "UNAUTHORIZED", 401)

        user_doc = frappe.db.get_value(
            "User", user,
            ["full_name", "email", "user_type"],
            as_dict=True
        )

        portal_info = None
        portal_user = frappe.db.get_value(
            "Customer Portal User",
            {"user": user, "is_active": 1},
            ["tenant", "portal_role"],
            as_dict=True
        )

        if portal_user:
            tenant = frappe.db.get_value(
                "Customer Portal Tenant",
                portal_user.tenant,
                ["tenant_name", "customer", "company",
                 "is_active", "enable_retention"],
                as_dict=True
            )
            customer = frappe.db.get_value(
                "Customer",
                tenant.customer,
                ["name", "customer_name", "customer_group"],
                as_dict=True
            ) if tenant else None

            portal_info = {
                "tenant": portal_user.tenant,
                "tenant_name": tenant.tenant_name if tenant else None,
                "portal_role": portal_user.portal_role,
                "customer": customer,
                "company": tenant.company if tenant else None,
                "features": {
                    "retention": bool(tenant.enable_retention) if tenant else False,
                }
            }

        return _success(data={
            "user": user,
            "full_name": user_doc.full_name,
            "email": user_doc.email,
            "user_type": user_doc.user_type,
            "portal": portal_info,
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_my_profile Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_retention_outstanding
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_retention_outstanding(company, customer=None):
    """
    Returns Sales Invoices that still have outstanding (unreleased) retention.

    Logic:
      outstanding = retention_amount
                  - sum(Retention Release.release_amount where docstatus=1)

    Args:
        company  (str): Company name (required)
        customer (str): Filter by customer (optional)

    Returns:
        dict: standard response with list of invoices
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            customer = portal_info["customer"]
            company = portal_info.get("company") or company
            if not portal_info.get("enable_retention"):
                return _error("Retention feature is not enabled for your account", "FEATURE_DISABLED", 403)

        filters = {
            "docstatus": 1,
            "company": company,
            "custom_retention_amount": [">", 0],
        }
        if customer:
            filters["customer"] = customer

        invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=[
                "name",
                "customer",
                "customer_name",
                "posting_date",
                "grand_total",
                "custom_retention_amount",
                "custom_net_after_retention",
                "custom_retention_jv",
            ],
            order_by="posting_date asc",
        )

        result = []
        for inv in invoices:
            retention_amount = flt(inv.custom_retention_amount)

            # Sum of all submitted Retention Release docs for this invoice
            released_rows = frappe.get_all(
                "Retention Release",
                filters={"sales_invoice": inv.name, "docstatus": 1},
                fields=["sum(release_amount) as total"],
            )
            total_released = flt(released_rows[0].total) if released_rows else 0.0

            retention_outstanding = retention_amount - total_released

            if retention_outstanding > 0.01:  # ignore rounding noise
                result.append(
                    {
                        "sales_invoice":         inv.name,
                        "customer":              inv.customer,
                        "customer_name":         inv.customer_name,
                        "posting_date":          str(inv.posting_date),
                        "grand_total":           flt(inv.grand_total),
                        "retention_amount":      retention_amount,
                        "total_released":        total_released,
                        "retention_outstanding": retention_outstanding,
                    }
                )

        return _success(data={"invoices": result, "total": len(result)})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_retention_summary
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_retention_summary(company):
    """
    Returns a summary of Retention status for the given company.

    Returns:
        dict: standard response with summary data
    """
    try:
        rows = frappe.db.sql(
            """
            SELECT
                COUNT(*)                                  AS total_invoices,
                COALESCE(SUM(custom_retention_amount), 0) AS total_retention
            FROM `tabSales Invoice`
            WHERE
                docstatus = 1
                AND company = %s
                AND custom_retention_amount > 0
            """,
            (company,),
            as_dict=True,
        )

        # Total released via Retention Release docs
        released_row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(rr.release_amount), 0) AS total_released
            FROM `tabRetention Release` rr
            INNER JOIN `tabSales Invoice` si
                ON si.name = rr.sales_invoice
            WHERE
                rr.docstatus = 1
                AND si.company = %s
            """,
            (company,),
            as_dict=True,
        )

        retention_account = frappe.db.get_value(
            "Company", company, "default_retention_account"
        )

        total_retention = flt(rows[0].total_retention) if rows else 0.0
        total_released  = flt(released_row[0].total_released) if released_row else 0.0

        result = {
            "total_invoices_with_retention": rows[0].total_invoices if rows else 0,
            "total_retention_amount":        total_retention,
            "total_retention_released":      total_released,
            "total_retention_outstanding":   total_retention - total_released,
            "retention_account":             retention_account or "NOT CONFIGURED",
        }

        return _success(data=result)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_invoice_retention_status
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_invoice_retention_status(sales_invoice):
    """
    Returns full retention status for a single Sales Invoice.

    Returns:
        dict: standard response with retention status data
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            if not portal_info.get("enable_retention"):
                return _error("Retention feature is not enabled for your account", "FEATURE_DISABLED", 403)
            inv_customer = frappe.db.get_value("Sales Invoice", sales_invoice, "customer")
            if inv_customer != portal_info["customer"]:
                return _error("Access denied", "PERMISSION_DENIED", 403)

        inv = frappe.db.get_value(
            "Sales Invoice",
            sales_invoice,
            ["custom_retention_amount", "custom_retention_jv", "customer", "company"],
            as_dict=True,
        )
        if not inv:
            frappe.throw(_("Sales Invoice {0} not found.").format(sales_invoice))

        retention_amount = flt(inv.custom_retention_amount)

        releases = frappe.get_all(
            "Retention Release",
            filters={"sales_invoice": sales_invoice, "docstatus": ["!=", 2]},
            fields=["name", "release_date", "release_amount", "status", "release_jv"],
            order_by="release_date asc",
        )

        total_released = sum(flt(r.release_amount) for r in releases if r.status in ("Submitted", "Paid"))

        result = {
            "sales_invoice":         sales_invoice,
            "customer":              inv.customer,
            "retention_jv":          inv.custom_retention_jv,
            "retention_amount":      retention_amount,
            "total_released":        total_released,
            "retention_outstanding": retention_amount - total_released,
            "releases":              releases,
        }

        return _success(data=result)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  make_retention_payment_entry
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def make_retention_payment_entry(retention_release):
    """
    Creates a Payment Entry (Draft) from a submitted Retention Release.

    The Release JV (created on Retention Release submit) adds release_amount back
    to the Sales Invoice outstanding via its DR Debtors reference. This PE then
    references the Sales Invoice directly so ERPNext tracks outstanding normally.

    Accounting:
        DR  Bank / Cash             = allocated_amount
        CR  AR (debit_to on SI)     = allocated_amount   [reference → Sales Invoice]

    Returns:
        dict: standard response with name of the newly created Payment Entry
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            rel_customer = frappe.db.get_value("Retention Release", retention_release, "customer")
            if rel_customer != portal_info["customer"]:
                return _error("Access denied", "PERMISSION_DENIED", 403)

        doc = frappe.get_doc("Retention Release", retention_release)

        if doc.docstatus != 1:
            return _error("Retention Release must be submitted first.", "NOT_SUBMITTED")

        if doc.status not in ("Submitted", "Released"):
            return _error(
                "Retention Release is not in Submitted status.",
                "WRONG_STATUS",
            )

        # ── Check Release JV exists ──────────────────────────────────────────────
        if not doc.release_jv:
            return _error(
                "No Release JV found. Please cancel and re-submit the Retention Release.",
                "NO_RELEASE_JV",
            )

        # ── Accounts ─────────────────────────────────────────────────────────────
        ar_account = frappe.db.get_value("Sales Invoice", doc.sales_invoice, "debit_to")
        if not ar_account:
            frappe.throw(
                _("Could not determine AR account from Sales Invoice {0}.").format(doc.sales_invoice)
            )

        retention_released_account = frappe.db.get_value(
            "Company", doc.company, "default_retention_released_account"
        )
        if not retention_released_account:
            return _error(
                "No Default Retention Released Account configured for this company.",
                "NO_RELEASED_ACCOUNT",
            )

        allocated    = flt(doc.release_amount)
        inv_project  = frappe.db.get_value("Sales Invoice", doc.sales_invoice, "project") or ""
        cost_center  = frappe.db.get_value("Company", doc.company, "cost_center") or ""

        # ── Step 1: Transfer JV — restores SI outstanding so the PE can reference it
        #
        #   DR  AR (Debtors) [ref: Sales Invoice]  = release_amount
        #   CR  1312 Retention Released Receivable  = release_amount
        #
        # The DR leg carries reference_type="Sales Invoice" (allowed because it uses
        # the SI's own debit_to account), which adds release_amount back to SI
        # outstanding and makes it collectable via the PE below.
        # ─────────────────────────────────────────────────────────────────────────
        transfer_jv = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": doc.company,
            "posting_date": today(),
            "user_remark": _(
                "Retention Payment Transfer — {0} — Invoice {1} — Customer {2}"
            ).format(doc.name, doc.sales_invoice, doc.customer),
            "accounts": [
                {
                    "account": ar_account,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "debit_in_account_currency": allocated,
                    "credit_in_account_currency": 0.0,
                    "reference_type": "Sales Invoice",
                    "reference_name": doc.sales_invoice,
                    "cost_center": cost_center,
                    "project": inv_project,
                },
                {
                    "account": retention_released_account,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "debit_in_account_currency": 0.0,
                    "credit_in_account_currency": allocated,
                    "cost_center": cost_center,
                    "project": inv_project,
                },
            ],
        })
        transfer_jv.flags.ignore_permissions = True
        transfer_jv.insert(ignore_permissions=True)
        transfer_jv.submit()

        # Patch against_voucher on the Retention Released leg (cannot carry
        # reference_type="Sales Invoice" since it is not the SI's debit_to account).
        frappe.db.sql(
            """UPDATE `tabGL Entry`
               SET against_voucher_type = 'Sales Invoice', against_voucher = %s
               WHERE voucher_no = %s AND account = %s AND is_cancelled = 0""",
            (doc.sales_invoice, transfer_jv.name, retention_released_account),
        )

        # Store the transfer JV on the Retention Release so it can be cancelled
        # if the Payment Entry is ever cancelled.
        frappe.db.set_value(
            "Retention Release", doc.name, "payment_transfer_jv", transfer_jv.name
        )

        # ── Step 2: Payment Entry — collects from the customer ───────────────────
        paid_to = frappe.db.get_value("Company", doc.company, "default_bank_account")
        if not paid_to:
            paid_to = frappe.db.get_value("Company", doc.company, "default_cash_account")
        if not paid_to:
            paid_to = frappe.db.get_value(
                "Account",
                {"company": doc.company, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
                "name",
            )
        if not paid_to:
            return _error(
                "No Bank or Cash account found. Please configure Default Bank Account in Company settings.",
                "NO_BANK_ACCOUNT",
            )

        ar_currency      = frappe.db.get_value("Account", ar_account, "account_currency")
        paid_to_currency = frappe.db.get_value("Account", paid_to, "account_currency")

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type               = "Receive"
        pe.company                    = doc.company
        pe.posting_date               = today()
        pe.party_type                 = "Customer"
        pe.party                      = doc.customer
        pe.paid_from                  = ar_account
        pe.paid_from_account_type     = "Receivable"
        pe.paid_from_account_currency = ar_currency
        pe.paid_to                    = paid_to
        pe.paid_to_account_currency   = paid_to_currency
        pe.source_exchange_rate       = 1
        pe.target_exchange_rate       = 1
        pe.paid_amount                = allocated
        pe.received_amount            = allocated
        pe.custom_retention_release   = doc.name
        pe.project                    = inv_project

        pe.append("references", {
            "reference_doctype":  "Sales Invoice",
            "reference_name":     doc.sales_invoice,
            "allocated_amount":   allocated,
            "outstanding_amount": allocated,
            "total_amount":       allocated,
            "project":            inv_project,
        })

        pe.remarks = _(
            "Retention payment for {0} — Invoice {1} — Customer {2}"
        ).format(doc.name, doc.sales_invoice, doc.customer)

        pe.setup_party_account_field()
        pe.set_missing_values()
        pe.insert(ignore_permissions=True)

        # ERPNext PE validate() recalculates outstanding_amount/total_amount from the
        # actual SI outstanding. Overwrite so the user sees the release_amount only.
        frappe.db.sql(
            """UPDATE `tabPayment Entry Reference`
               SET outstanding_amount = %s, total_amount = %s
               WHERE parent = %s
                 AND reference_doctype = 'Sales Invoice'
                 AND reference_name = %s""",
            (allocated, allocated, pe.name, doc.sales_invoice),
        )

        return _success(data={"name": pe.name})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_customer_invoices
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_customer_invoices(customer, company=None):
    """
    Returns all submitted Sales Invoices for a customer.
    Includes retention info for each invoice.

    Args:
        customer (str): Customer name (required)
        company (str): Company filter (optional)

    Returns:
        dict: standard response with list of invoices
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            customer = portal_info["customer"]
            company = portal_info.get("company") or company

        if not customer:
            return _error("Customer is required", "MISSING_CUSTOMER")

        filters = {
            "docstatus": 1,
            "customer": customer,
        }
        if company:
            filters["company"] = company

        invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=[
                "name",
                "customer",
                "customer_name",
                "posting_date",
                "due_date",
                "grand_total",
                "outstanding_amount",
                "status",
                "custom_retention_amount",
                "custom_retention_percentage",
                "company",
            ],
            order_by="posting_date desc",
        )

        for inv in invoices:
            inv["has_retention"] = flt(inv.custom_retention_amount) > 0

        return _success(data={"invoices": invoices, "total": len(invoices)})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_customer_invoices Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_customer_retention_releases
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_customer_retention_releases(customer, company=None, status=None):
    """
    Returns all Retention Releases for a customer.

    Args:
        customer (str): Customer name (required)
        company (str): Company filter (optional)
        status (str): Filter by status - Draft/Submitted/Paid/Cancelled (optional)

    Returns:
        dict: standard response with list of releases
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            customer = portal_info["customer"]
            company = portal_info.get("company") or company
            if not portal_info.get("enable_retention"):
                return _error("Retention feature is not enabled for your account", "FEATURE_DISABLED", 403)

        if not customer:
            return _error("Customer is required", "MISSING_CUSTOMER")

        filters = {"customer": customer, "docstatus": ["!=", 2]}
        if company:
            filters["company"] = company
        if status:
            filters["status"] = status

        releases = frappe.get_all(
            "Retention Release",
            filters=filters,
            fields=[
                "name",
                "customer",
                "company",
                "sales_invoice",
                "release_date",
                "release_amount",
                "remaining_after_release",
                "status",
                "release_jv",
                "creation",
            ],
            order_by="release_date desc",
        )

        return _success(data={"releases": releases, "total": len(releases)})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_customer_retention_releases Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  create_retention_release
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_retention_release(sales_invoice, release_amount, release_date=None, notes=None):
    """
    Creates and submits a Retention Release from API.

    Args:
        sales_invoice (str): Sales Invoice name (required)
        release_amount (float): Amount to release (required)
        release_date (str): Release date - defaults to today (optional)
        notes (str): Notes (optional)

    Returns:
        dict: standard response with created release details
    """
    try:
        portal_info = _get_portal_customer()

        if not sales_invoice:
            return _error("Sales Invoice is required", "MISSING_INVOICE")
        if not flt(release_amount):
            return _error("Release Amount is required", "MISSING_AMOUNT")

        # Check retention feature for portal users
        if portal_info and not portal_info.get("enable_retention"):
            return _error("Retention feature is not enabled for your account", "FEATURE_DISABLED", 403)

        # Get invoice details
        inv = frappe.db.get_value(
            "Sales Invoice",
            sales_invoice,
            ["docstatus", "customer", "company", "custom_retention_amount", "due_date"],
            as_dict=True
        )

        if not inv:
            return _error(f"Sales Invoice {sales_invoice} not found", "INVOICE_NOT_FOUND", 404)

        if portal_info and inv.customer != portal_info["customer"]:
            return _error("Access denied", "PERMISSION_DENIED", 403)

        if inv.docstatus != 1:
            return _error("Sales Invoice must be submitted", "INVOICE_NOT_SUBMITTED")

        if not flt(inv.custom_retention_amount):
            return _error("Sales Invoice has no retention amount", "NO_RETENTION")

        # Check outstanding retention
        status = get_invoice_retention_status(sales_invoice)
        outstanding = flt(status["data"]["retention_outstanding"])

        if flt(release_amount) > outstanding:
            return _error(
                f"Release Amount ({release_amount}) exceeds outstanding retention ({outstanding})",
                "EXCEEDS_OUTSTANDING"
            )

        # Create Retention Release
        doc = frappe.new_doc("Retention Release")
        doc.update({
            "sales_invoice": sales_invoice,
            "customer": inv.customer,
            "company": inv.company,
            "release_date": release_date or today(),
            "release_amount": flt(release_amount),
            "due_date": inv.due_date,
            "notes": notes,
        })
        doc.insert(ignore_permissions=True)
        doc.submit()

        return _success(
            data={
                "name": doc.name,
                "status": doc.status,
                "release_amount": doc.release_amount,
                "sales_invoice": doc.sales_invoice,
                "release_jv": doc.release_jv,
            },
            message=f"Retention Release {doc.name} created successfully"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_retention_release Error")
        return _error(str(e))


# ──────────────────────────────────────────────────────────────────────────────
#  get_retention_dashboard
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_retention_dashboard(company, customer=None):
    """
    Returns complete retention dashboard data.
    Single endpoint for portal home page.

    Returns:
        dict: summary + outstanding invoices + recent releases
    """
    try:
        portal_info = _get_portal_customer()
        if portal_info:
            customer = portal_info["customer"]
            company = portal_info.get("company") or company
            if not portal_info.get("enable_retention"):
                return _error("Retention feature is not enabled for your account", "FEATURE_DISABLED", 403)

        summary = get_retention_summary(company)
        outstanding = get_retention_outstanding(company, customer)

        filters = {"docstatus": ["!=", 2]}
        if customer:
            filters["customer"] = customer

        recent_releases = frappe.get_all(
            "Retention Release",
            filters=filters,
            fields=["name", "customer", "sales_invoice", "release_date",
                   "release_amount", "status"],
            order_by="release_date desc",
            limit=10
        )

        return _success(data={
            "summary": summary["data"] if summary.get("success") else summary,
            "outstanding_invoices": outstanding["data"]["invoices"] if outstanding.get("success") else outstanding,
            "recent_releases": recent_releases,
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_retention_dashboard Error")
        return _error(str(e))
