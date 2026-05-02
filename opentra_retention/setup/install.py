import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    """Called after app install and after migrate."""
    try:
        add_receivable_retention_account_type()
        create_retention_custom_fields()
        frappe.db.commit()  # flush schema changes so account creation can read the new columns
        create_retention_print_format()
        add_to_selling_workspace()
        add_report_to_workspaces()
        create_portal_user_role()
        create_user_customer_field()
        create_retention_accounts()
        frappe.db.commit()
        print("✅ opentra_retention: custom fields, account type, print format, accounts, workspace, and portal role installed.")
    except Exception as e:
        frappe.log_error(f"opentra_retention install error: {e}", "Retention Install")
        print(f"❌ opentra_retention install error: {e}")


def add_receivable_retention_account_type():
    """Add 'Receivable Retention' to Account.account_type select options."""
    try:
        current_options = frappe.db.get_value(
            "DocField",
            {"parent": "Account", "fieldname": "account_type"},
            "options",
        )
        if current_options and "Receivable Retention" not in current_options:
            new_options = current_options + "\nReceivable Retention"
            # Use property setter to avoid modifying core DocType directly
            if frappe.db.exists(
                "Property Setter",
                {"doc_type": "Account", "field_name": "account_type", "property": "options"},
            ):
                frappe.db.set_value(
                    "Property Setter",
                    {"doc_type": "Account", "field_name": "account_type", "property": "options"},
                    "value",
                    new_options,
                )
            else:
                frappe.make_property_setter(
                    {
                        "doctype": "Account",
                        "fieldname": "account_type",
                        "property": "options",
                        "value": new_options,
                        "property_type": "Text",
                    }
                )
            frappe.clear_cache(doctype="Account")
            print("  + Account Type 'Receivable Retention' added.")
    except Exception as e:
        print(f"  ! Could not add account type: {e}")


def create_retention_custom_fields():
    """Create all custom fields for Retention on Company, Sales Invoice, Payment Entry."""

    custom_fields = {
        # ── Company ──────────────────────────────────────────────────────────
        "Company": [
            {
                "fieldname": "retention_section",
                "fieldtype": "Section Break",
                "label": "Retention Settings",
                "insert_after": "asset_received_but_not_billed",
                "collapsible": 0,
            },
            {
                "fieldname": "default_retention_account",
                "fieldtype": "Link",
                "options": "Account",
                "label": "Default Retention Receivable Account",
                "insert_after": "retention_section",
                "description": "Account used for Retention deductions (Receivable Retention type)",
            },
            {
                "fieldname": "default_retention_released_account",
                "fieldtype": "Link",
                "options": "Account",
                "label": "Default Retention Released Account",
                "insert_after": "default_retention_account",
                "description": "Account for approved but unpaid retention releases (Receivable type)",
            },
        ],

        # ── Payment Entry ────────────────────────────────────────────────────
        "Payment Entry": [
            {
                "fieldname": "custom_retention_release",
                "fieldtype": "Link",
                "options": "Retention Release",
                "label": "Retention Release",
                "insert_after": "remarks",
                "read_only": 1,
                "no_copy": 1,
                "description": "Set when PE is created from a Retention Release. Used to mark the release as Paid on submit.",
            },
        ],

        # ── Sales Invoice ────────────────────────────────────────────────────
        "Sales Invoice": [
            {
                "fieldname": "retention_section",
                "fieldtype": "Section Break",
                "label": "Retention",
                "insert_after": "rounded_total",
                "collapsible": 1,
            },
            {
                "fieldname": "custom_retention_percentage",
                "fieldtype": "Select",
                "label": "Retention %",
                "options": "\n10%\n5%",
                "insert_after": "retention_section",
                "description": "Select percentage to auto-calculate, or leave empty to enter manually",
            },
            {
                "fieldname": "col_break_retention",
                "fieldtype": "Column Break",
                "insert_after": "custom_retention_percentage",
            },
            {
                "fieldname": "custom_retention_amount",
                "fieldtype": "Currency",
                "label": "Retention Amount",
                "options": "currency",
                "insert_after": "col_break_retention",
                "description": "Auto-calculated when % selected; editable if % is empty",
            },
            {
                "fieldname": "col_break_retention_2",
                "fieldtype": "Column Break",
                "insert_after": "custom_retention_amount",
            },
            {
                "fieldname": "custom_net_after_retention",
                "fieldtype": "Currency",
                "label": "Net After Retention",
                "options": "currency",
                "insert_after": "col_break_retention_2",
                "read_only": 1,
                "description": "Grand Total minus Retention Amount",
            },
            {
                "fieldname": "custom_retention_jv",
                "fieldtype": "Link",
                "options": "Journal Entry",
                "label": "Retention Journal Entry",
                "insert_after": "custom_net_after_retention",
                "read_only": 1,
                "no_copy": 1,
                "description": "Auto-created JV that moves Retention from AR to Retention Receivable",
            },
        ],

    }

    create_custom_fields(custom_fields, ignore_validate=True)
    frappe.clear_cache()
    print("  + Custom fields created on Company, Sales Invoice, Payment Entry.")


def create_retention_print_format():
    """
    Create (or update) the 'Retention Invoice' Print Format for Retention Release.
    This is a non-tax invoice to be sent to the customer before payment.
    Supports partial payment: shows release_amount as the amount due.
    """
    PF_NAME = "Retention Invoice"

    html = r"""
{%- set company_doc = frappe.get_doc("Company", doc.company) %}
{%- set inv = frappe.db.get_value(
        "Sales Invoice", doc.sales_invoice,
        ["grand_total", "currency", "posting_date", "customer_name"],
        as_dict=True) or {} %}
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Arial', sans-serif; font-size: 13px; color: #222; direction: rtl; }

  .page-wrapper { padding: 20px 30px; max-width: 860px; margin: 0 auto; }

  /* ── Header ── */
  .inv-header { display: flex; justify-content: space-between; align-items: flex-start;
                border-bottom: 3px solid #1a5276; padding-bottom: 14px; margin-bottom: 18px; }
  .company-info h1 { font-size: 20px; color: #1a5276; }
  .company-info p  { font-size: 11px; color: #555; margin-top: 2px; }
  .inv-title-block { text-align: center; }
  .inv-title { font-size: 22px; font-weight: bold; color: #1a5276; }
  .inv-subtitle { font-size: 12px; color: #888; margin-top: 4px; }
  .non-tax-badge {
    display: inline-block; background: #fef9e7; border: 1px solid #f39c12;
    color: #b7770d; font-size: 11px; font-weight: bold;
    padding: 3px 10px; border-radius: 4px; margin-top: 6px;
  }
  .inv-number-block { text-align: left; font-size: 12px; color: #555; }
  .inv-number-block strong { font-size: 15px; color: #1a5276; display: block; }

  /* ── Info Grid ── */
  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
  .info-box { background: #f4f6f7; border-right: 4px solid #1a5276; padding: 10px 14px; border-radius: 4px; }
  .info-box h3 { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .info-box p  { font-size: 13px; color: #222; }
  .info-box p span { color: #555; font-size: 12px; }

  /* ── Details Table ── */
  .details-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  .details-table th {
    background: #1a5276; color: #fff; padding: 9px 12px;
    font-size: 12px; font-weight: bold; text-align: right;
  }
  .details-table td { padding: 9px 12px; border-bottom: 1px solid #e5e5e5; font-size: 13px; }
  .details-table tr:nth-child(even) td { background: #f9f9f9; }
  .details-table .amount { font-weight: bold; color: #1a5276; }

  /* ── Totals ── */
  .totals-section { display: flex; justify-content: flex-end; margin-bottom: 20px; }
  .totals-box { width: 320px; border: 1px solid #d5d8dc; border-radius: 4px; overflow: hidden; }
  .totals-row { display: flex; justify-content: space-between; padding: 8px 14px;
                border-bottom: 1px solid #e5e5e5; font-size: 13px; }
  .totals-row:last-child { border-bottom: none; }
  .totals-row.grand { background: #1a5276; color: #fff; font-weight: bold; font-size: 15px; }
  .totals-row .label { color: #666; }
  .totals-row.grand .label { color: #d0e4f0; }

  /* ── Notes ── */
  .notes-box { background: #eaf2ff; border: 1px solid #aed6f1; border-radius: 4px;
               padding: 10px 14px; margin-bottom: 20px; font-size: 12px; color: #1a5276; }
  .notes-box strong { display: block; margin-bottom: 4px; }

  /* ── Footer ── */
  .inv-footer { text-align: center; font-size: 11px; color: #aaa;
                border-top: 1px solid #e5e5e5; padding-top: 12px; margin-top: 10px; }
</style>
</head>
<body>
<div class="page-wrapper">

  <!-- ══ HEADER ══════════════════════════════════════════════════════ -->
  <div class="inv-header">

    <div class="company-info">
      <h1>{{ company_doc.company_name }}</h1>
      {% if company_doc.address %}<p>{{ company_doc.address }}</p>{% endif %}
      {% if company_doc.phone_no %}<p>هاتف: {{ company_doc.phone_no }}</p>{% endif %}
    </div>

    <div class="inv-title-block">
      <div class="inv-title">فاتورة استحقاق ضمان الأداء</div>
      <div class="inv-subtitle">Retention Release Invoice</div>
      <div class="non-tax-badge">⚠ غير خاضعة لضريبة القيمة المضافة</div>
    </div>

    <div class="inv-number-block">
      <strong>{{ doc.name }}</strong>
      <span>رقم الفاتورة</span>
      <br><br>
      <span>{{ frappe.format(doc.release_date, {"fieldtype": "Date"}) }}</span><br>
      <span>تاريخ الإصدار</span>
    </div>

  </div>

  <!-- ══ INFO GRID ════════════════════════════════════════════════════ -->
  <div class="info-grid">

    <div class="info-box">
      <h3>بيانات العميل</h3>
      <p>{{ inv.get("customer_name") or doc.customer }}</p>
      <p><span>كود العميل: {{ doc.customer }}</span></p>
    </div>

    <div class="info-box">
      <h3>الفاتورة المرجعية</h3>
      <p>{{ doc.sales_invoice }}</p>
      {% if inv.get("posting_date") %}
      <p><span>تاريخ الفاتورة: {{ frappe.format(inv.posting_date, {"fieldtype": "Date"}) }}</span></p>
      {% endif %}
    </div>

    <div class="info-box">
      <h3>الشركة</h3>
      <p>{{ doc.company }}</p>
    </div>

    <div class="info-box">
      <h3>حالة الإفراج</h3>
      <p>{{ doc.status }}</p>
      {% if doc.release_jv %}
      <p><span>قيد الإفراج: {{ doc.release_jv }}</span></p>
      {% endif %}
    </div>

  </div>

  <!-- ══ DETAILS TABLE ════════════════════════════════════════════════ -->
  <table class="details-table">
    <thead>
      <tr>
        <th>البيان</th>
        <th>التفاصيل</th>
        <th>المبلغ ({{ inv.get("currency") or "SAR" }})</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>إجمالي فاتورة المبيعات</td>
        <td>{{ doc.sales_invoice }}</td>
        <td class="amount">{{ "{:,.2f}".format(inv.get("grand_total") or 0) }}</td>
      </tr>
      <tr>
        <td>إجمالي مبلغ الضمان المحتجز</td>
        <td>المبلغ المحتجز من الفاتورة الأصلية</td>
        <td class="amount">{{ "{:,.2f}".format(doc.retention_amount or 0) }}</td>
      </tr>
      <tr>
        <td><strong>مبلغ الإفراج المستحق (هذه الفاتورة)</strong></td>
        <td>
          {%- set already = namespace(val=0) %}
          {%- set prev_releases = frappe.get_all(
                "Retention Release",
                filters={"sales_invoice": doc.sales_invoice, "docstatus": 1, "name": ["!=", doc.name]},
                fields=["sum(release_amount) as total"]) %}
          {%- if prev_releases and prev_releases[0].total %}
            {%- set already.val = prev_releases[0].total %}
          {%- endif %}
          {%- if already.val > 0 %}
            مسبق الإفراج: {{ "{:,.2f}".format(already.val) }}
          {%- else %}
            إفراج أول / كامل
          {%- endif %}
        </td>
        <td class="amount" style="font-size:15px; color:#1a5276;">
          {{ "{:,.2f}".format(doc.release_amount or 0) }}
        </td>
      </tr>
    </tbody>
  </table>

  <!-- ══ TOTALS ═══════════════════════════════════════════════════════ -->
  <div class="totals-section">
    <div class="totals-box">
      <div class="totals-row">
        <span class="label">الضريبة المضافة (VAT)</span>
        <span>0.00</span>
      </div>
      <div class="totals-row grand">
        <span class="label">الإجمالي المستحق للسداد</span>
        <span>{{ "{:,.2f}".format(doc.release_amount or 0) }} {{ inv.get("currency") or "SAR" }}</span>
      </div>
    </div>
  </div>

  <!-- ══ NOTES ════════════════════════════════════════════════════════ -->
  <div class="notes-box">
    <strong>📌 ملاحظات:</strong>
    هذه الفاتورة غير خاضعة لضريبة القيمة المضافة وفق المادة المعفاة.
    يمكن السداد جزئياً أو كاملاً. المبلغ المدرج أعلاه هو الحد الأقصى المستحق في هذه المرحلة.
    {% if doc.notes %}<br>{{ doc.notes }}{% endif %}
  </div>

  <!-- ══ FOOTER ════════════════════════════════════════════════════════ -->
  <div class="inv-footer">
    تم إنشاء هذه الفاتورة بواسطة نظام Opentra Retention — {{ frappe.format(frappe.utils.today(), {"fieldtype": "Date"}) }}
  </div>

</div>
</body>
</html>
"""

    try:
        if frappe.db.exists("Print Format", PF_NAME):
            pf = frappe.get_doc("Print Format", PF_NAME)
            pf.html = html
            pf.save(ignore_permissions=True)
            print(f"  + Print Format '{PF_NAME}' updated.")
        else:
            pf = frappe.get_doc({
                "doctype":           "Print Format",
                "name":              PF_NAME,
                "doc_type":          "Retention Release",
                "module":            "Opentra Retention",
                "print_format_type": "Jinja",
                "html":              html,
                "disabled":          0,
                "standard":          "No",
            })
            pf.flags.ignore_permissions = True
            pf.insert(ignore_permissions=True)
            print(f"  + Print Format '{PF_NAME}' created.")
    except Exception as e:
        print(f"  ! Could not create Print Format '{PF_NAME}': {e}")


def add_report_to_workspaces():
    """Add Retention Status Report link to Accounting and Selling workspaces. Idempotent."""
    for ws_name in ("Accounting", "Selling"):
        try:
            if not frappe.db.exists("Workspace", ws_name):
                print(f"  ! {ws_name} workspace not found — skipping report link.")
                continue

            ws = frappe.get_doc("Workspace", ws_name)

            existing = [getattr(lnk, "link_to", "") for lnk in ws.links]
            if "Retention Status Report" in existing:
                print(f"  + Retention Status Report already in {ws_name} workspace — skipping.")
                continue

            ws.append("links", {
                "type":            "Link",
                "label":           "Retention Status Report",
                "link_type":       "Report",
                "link_to":         "Retention Status Report",
                "idx":             999,
                "is_query_report": 1,
                "onboard":         0,
                "dependencies":    "",
                "hidden":          0,
            })
            ws.save(ignore_permissions=True)
            frappe.db.commit()
            print(f"  + Retention Status Report added to {ws_name} workspace.")
        except Exception as exc:
            frappe.log_error(title=f"Retention Workspace Install Error ({ws_name})", message=str(exc))
            print(f"  ! Could not add report to {ws_name} workspace: {exc}")


def add_to_selling_workspace():
    """
    Add a 'Retention Release' link to the ERPNext Selling workspace so it
    appears under Reports & Masters > Selling on the home page.
    Safe to call multiple times (idempotent).
    """
    try:
        if not frappe.db.exists("Workspace", "Selling"):
            print("  ! Selling workspace not found — skipping.")
            return

        workspace = frappe.get_doc("Workspace", "Selling")

        # Remove ALL existing rows for Retention Release (correct or stale)
        workspace.links = [
            lnk for lnk in workspace.links
            if getattr(lnk, "link_to", "") != "Retention Release"
        ]

        # Append a correct DocType link entry with all required Frappe v15 fields
        workspace.append("links", {
            "type":            "Link",
            "label":           "Retention Release",
            "link_type":       "DocType",
            "link_to":         "Retention Release",
            "idx":             999,
            "is_query_report": 0,
            "onboard":         0,
            "dependencies":    "",
            "hidden":          0,
        })
        workspace.save(ignore_permissions=True)
        frappe.db.commit()
        print("  + Retention Release added to Selling workspace.")

    except Exception as exc:
        frappe.log_error(
            title="Retention Workspace Install Error",
            message=str(exc),
        )
        print(f"  ! Could not add Retention Release to Selling workspace: {exc}")


def create_portal_user_role():
    """Create the 'Retention Portal User' role for external portal users."""
    try:
        if not frappe.db.exists("Role", "Retention Portal User"):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": "Retention Portal User",
                "desk_access": 0,
                "is_custom": 1,
            }).insert(ignore_permissions=True)
            print("  + Role 'Retention Portal User' created.")
        else:
            print("  + Role 'Retention Portal User' already exists — skipping.")
    except Exception as e:
        print(f"  ! Could not create Role 'Retention Portal User': {e}")


def create_user_customer_field():
    """Create custom_customer field on User doctype for portal customer linking."""
    try:
        if not frappe.db.exists("Custom Field", "User-custom_customer"):
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "User",
                "fieldname": "custom_customer",
                "label": "Customer",
                "fieldtype": "Link",
                "options": "Customer",
                "insert_after": "email",
                "description": "Linked customer for Portal API access",
            }).insert(ignore_permissions=True)
            frappe.clear_cache(doctype="User")
            print("  + Custom Field 'User-custom_customer' created.")
        else:
            print("  + Custom Field 'User-custom_customer' already exists — skipping.")
    except Exception as e:
        print(f"  ! Could not create Custom Field 'User-custom_customer': {e}")


def create_retention_accounts():
    """
    Auto-create 1311 Retention Receivable and 1312 Retention Released Receivable
    accounts for every company that does not already have them, then set as Company
    defaults. Safe to call multiple times (idempotent).
    """
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    if not companies:
        print("  + No companies found — accounts will be created when first company is added.")
        return
    for co in companies:
        _create_company_retention_accounts(co.name, co.abbr)


def _create_company_retention_accounts(company, abbr):
    """
    Create the two retention accounts for a single company and wire them into
    Company defaults. Called by create_retention_accounts() (install) and
    on_company_created() (new company hook).
    """
    # Locate the parent Accounts Receivable group: use the parent of the Debtors account.
    ar_account = frappe.db.get_value("Company", company, "default_receivable_account")
    if not ar_account:
        ar_account = frappe.db.get_value(
            "Account",
            {"company": company, "account_type": "Receivable", "is_group": 0},
            "name",
        )
    if not ar_account:
        print(f"  ! No Receivable account found for {company} — skipping retention account creation.")
        return

    ar_parent = frappe.db.get_value("Account", ar_account, "parent_account")
    if not ar_parent:
        print(f"  ! Cannot determine AR parent account for {company} — skipping.")
        return

    created_1311 = None
    created_1312 = None

    # ── 1311 Retention Receivable (Receivable Retention type) ────────────────
    existing_1311 = frappe.db.get_value(
        "Account", {"account_name": "Retention Receivable", "company": company}, "name"
    )
    if existing_1311:
        print(f"  + {existing_1311} already exists for {company} — skipping.")
        created_1311 = existing_1311
    else:
        try:
            doc = frappe.get_doc({
                "doctype":        "Account",
                "account_name":   "Retention Receivable",
                "account_number": "1311",
                "account_type":   "Receivable Retention",
                "parent_account": ar_parent,
                "company":        company,
                "is_group":       0,
                "root_type":      "Asset",
                "report_type":    "Balance Sheet",
            })
            doc.insert(ignore_permissions=True)
            created_1311 = doc.name
            print(f"  + Created {created_1311} for {company}.")
        except Exception as e:
            print(f"  ! Could not create 1311 Retention Receivable for {company}: {e}")

    # ── 1312 Retention Released Receivable (standard Receivable type) ─────────
    existing_1312 = frappe.db.get_value(
        "Account", {"account_name": "Retention Released Receivable", "company": company}, "name"
    )
    if existing_1312:
        print(f"  + {existing_1312} already exists for {company} — skipping.")
        created_1312 = existing_1312
    else:
        try:
            doc = frappe.get_doc({
                "doctype":        "Account",
                "account_name":   "Retention Released Receivable",
                "account_number": "1312",
                "account_type":   "Receivable",
                "parent_account": ar_parent,
                "company":        company,
                "is_group":       0,
                "root_type":      "Asset",
                "report_type":    "Balance Sheet",
            })
            doc.insert(ignore_permissions=True)
            created_1312 = doc.name
            print(f"  + Created {created_1312} for {company}.")
        except Exception as e:
            print(f"  ! Could not create 1312 Retention Released Receivable for {company}: {e}")

    # ── Set as Company defaults (only if not already configured) ─────────────
    updates = {}
    if created_1311 and not frappe.db.get_value("Company", company, "default_retention_account"):
        updates["default_retention_account"] = created_1311
    if created_1312 and not frappe.db.get_value("Company", company, "default_retention_released_account"):
        updates["default_retention_released_account"] = created_1312
    if updates:
        frappe.db.set_value("Company", company, updates)
        print(f"  + Set retention account defaults for {company}.")


def on_company_created(doc, method=None):
    """
    Hook: fires on Company after_insert. Auto-creates the two retention accounts
    for the new company. ERPNext sets up its default CoA in its own after_insert
    hook (which runs before ours), so the AR account should already exist.
    """
    try:
        _create_company_retention_accounts(doc.name, doc.abbr)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            title="Retention Account Setup Error",
            message=f"Could not create retention accounts for {doc.name}: {e}",
        )
