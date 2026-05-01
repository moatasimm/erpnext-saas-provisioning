import frappe
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    return columns, data


def get_columns():
    return [
        {"label": "Sales Invoice", "fieldname": "sales_invoice",
         "fieldtype": "Link", "options": "Sales Invoice", "width": 180},
        {"label": "Customer", "fieldname": "customer",
         "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "Project", "fieldname": "project",
         "fieldtype": "Link", "options": "Project", "width": 120},
        {"label": "Invoice Date", "fieldname": "posting_date",
         "fieldtype": "Date", "width": 100},
        {"label": "Grand Total", "fieldname": "grand_total",
         "fieldtype": "Currency", "width": 130},
        {"label": "Retention %", "fieldname": "retention_pct",
         "fieldtype": "Data", "width": 100},
        {"label": "Retention Total", "fieldname": "retention_total",
         "fieldtype": "Currency", "width": 130},
        {"label": "Retention Held (1311)", "fieldname": "retention_held",
         "fieldtype": "Currency", "width": 150},
        {"label": "Retention Released (1312)", "fieldname": "retention_released",
         "fieldtype": "Currency", "width": 160},
        {"label": "Retention Paid", "fieldname": "retention_paid",
         "fieldtype": "Currency", "width": 130},
        {"label": "Retention Outstanding", "fieldname": "retention_outstanding",
         "fieldtype": "Currency", "width": 160},
        {"label": "Status", "fieldname": "status",
         "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    customer = filters.get("customer")
    project = filters.get("project")

    conditions = "si.docstatus = 1 AND si.company = %(company)s AND si.custom_retention_amount > 0"
    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
    if customer:
        conditions += " AND si.customer = %(customer)s"
    if project:
        conditions += " AND si.project = %(project)s"

    invoices = frappe.db.sql(
        f"""
        SELECT
            si.name          AS sales_invoice,
            si.customer,
            si.project,
            si.posting_date,
            si.grand_total,
            si.custom_retention_percentage AS retention_pct,
            si.custom_retention_amount     AS retention_total
        FROM `tabSales Invoice` si
        WHERE {conditions}
        ORDER BY si.posting_date DESC
        """,
        filters,
        as_dict=True,
    )

    retention_account = frappe.db.get_value("Company", company, "default_retention_account")
    retention_released_account = frappe.db.get_value(
        "Company", company, "default_retention_released_account"
    )

    status_filter = filters.get("retention_status")
    data = []

    for inv in invoices:
        retention_total = flt(inv.retention_total)
        si_name = inv.sales_invoice

        retention_held = flt(
            frappe.db.sql(
                """
                SELECT COALESCE(SUM(debit) - SUM(credit), 0)
                FROM `tabGL Entry`
                WHERE account = %s
                  AND against_voucher = %s
                  AND against_voucher_type = 'Sales Invoice'
                  AND is_cancelled = 0
                """,
                (retention_account, si_name),
            )[0][0]
        )

        retention_released = flt(
            frappe.db.sql(
                """
                SELECT COALESCE(SUM(debit) - SUM(credit), 0)
                FROM `tabGL Entry`
                WHERE account = %s
                  AND against_voucher = %s
                  AND against_voucher_type = 'Sales Invoice'
                  AND is_cancelled = 0
                """,
                (retention_released_account, si_name),
            )[0][0]
        ) if retention_released_account else 0.0

        retention_paid = retention_total - retention_held - retention_released
        retention_outstanding = retention_held + retention_released

        if retention_outstanding <= 0.01:
            status = "Fully Released"
        elif retention_held <= 0.01:
            status = "Pending Payment"
        else:
            status = "Active"

        if status_filter == "Has Outstanding Retention" and retention_outstanding <= 0.01:
            continue
        if status_filter == "Fully Released" and retention_outstanding > 0.01:
            continue

        data.append({
            "sales_invoice":       si_name,
            "customer":            inv.customer,
            "project":             inv.project,
            "posting_date":        inv.posting_date,
            "grand_total":         inv.grand_total,
            "retention_pct":       inv.retention_pct,
            "retention_total":     retention_total,
            "retention_held":      retention_held,
            "retention_released":  retention_released,
            "retention_paid":      retention_paid,
            "retention_outstanding": retention_outstanding,
            "status":              status,
        })

    return data
