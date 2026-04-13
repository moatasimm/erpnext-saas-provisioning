"""
POC v2: Retention via Journal Entry (Hook-only approach)
========================================================

V2 CHANGES from v1:
    - Set `taxes_and_charges` template to satisfy ksa_compliance validation
    - Set `tax_category = "Standard"` (per Gotcha #1 in DECISIONS.md v0.4)
    - Added cleanup helper at the top for easy re-runs

PURPOSE:
    Validate the critical assumption that underpins the hook-only design:

    "A Journal Entry crediting Debtors with against_voucher=<invoice_name>
     will be recognized by ERPNext as reducing the invoice's
     outstanding_amount — without any code override."

SCENARIO (matches the spec document example):
    Net total        = 500,000
    VAT 15%          =  75,000
    Grand total      = 575,000
    Retention (10%)  =  50,000  (on net, no VAT)

    Expected combined ledger:
        Dr. Debtors                 525,000  (575k from invoice - 50k from JE)
        Dr. Retention Receivable     50,000
            Cr. Sales                   500,000
            Cr. VAT Output 15%           75,000

    CRITICAL CHECK: outstanding_amount after JE should be 525,000.

USAGE:
    cd /tmp && \
    wget https://raw.githubusercontent.com/moatasimm/erpnext-saas-provisioning/main/poc_retention_je.py \
        -O poc_retention_je.py && \
    sudo chown frappe:frappe /tmp/poc_retention_je.py && \
    sudo -iu frappe bash -c "cd /home/frappe/frappe-bench && \
        bench --site ksatest.opentra.opentech.sa console" <<'STDIN'
    exec(open('/tmp/poc_retention_je.py').read())
    exit()
    STDIN

    NOTE: If running via `%run` in ipython, the script executes but
    `exec(open(...))` is more reliable for stdin heredoc mode.
"""

import frappe
from frappe.utils import flt, nowdate, add_days

COMPANY = "KSA Test Company"
ABBR = "KTC"
CUSTOMER = "Test B2B Customer"
ITEM = "TEST-ITEM-01"
TAX_TEMPLATE = f"KSA VAT 15% - {ABBR}"


# =============================================================================
# Helper: clean up any previous POC runs
# =============================================================================

def cleanup_previous_runs():
    """Cancel any prior POC journal entries and invoices for idempotent re-runs."""
    cancelled = 0

    # Cancel POC journal entries (matched by user_remark)
    for je_name in frappe.db.sql_list("""
        SELECT name FROM `tabJournal Entry`
        WHERE docstatus = 1 AND user_remark LIKE 'Retention reclassification%'
    """):
        try:
            doc = frappe.get_doc("Journal Entry", je_name)
            doc.cancel()
            cancelled += 1
        except Exception:
            pass

    # Cancel POC invoices (matched by grand_total + customer)
    for si_name in frappe.db.sql_list("""
        SELECT name FROM `tabSales Invoice`
        WHERE docstatus = 1 AND grand_total = 575000 AND customer = %s
    """, CUSTOMER):
        try:
            doc = frappe.get_doc("Sales Invoice", si_name)
            doc.cancel()
            cancelled += 1
        except Exception:
            pass

    if cancelled:
        frappe.db.commit()
        print(f"  → Cleaned up {cancelled} previous POC document(s)")


# =============================================================================
# Setup: ensure Retention account exists
# =============================================================================

def ensure_retention_account():
    name = f"Retention Receivable - {ABBR}"

    if frappe.db.exists("Account", name):
        print(f"  → Retention account exists: {name}")
        return name

    parent = frappe.db.get_value(
        "Account",
        {
            "company": COMPANY,
            "account_name": ["like", "%Accounts Receivable%"],
            "is_group": 1,
        },
        "name",
    )

    acc = frappe.new_doc("Account")
    acc.account_name = "Retention Receivable"
    acc.company = COMPANY
    acc.parent_account = parent
    acc.account_type = "Receivable"
    acc.account_currency = "SAR"
    acc.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  → Created: {acc.name}")
    return acc.name


# =============================================================================
# Step 1: Create a standard Sales Invoice with proper VAT template
# =============================================================================

def create_standard_invoice():
    """
    Create an invoice that satisfies ksa_compliance validations:
      - Uses Sales Taxes and Charges Template (not manual tax rows)
      - Sets tax_category to "Standard"
      - Company is KSA-configured (done in prior session setup)
    """
    # Verify the template exists before proceeding
    if not frappe.db.exists("Sales Taxes and Charges Template", TAX_TEMPLATE):
        frappe.throw(
            f"Sales Taxes and Charges Template '{TAX_TEMPLATE}' not found. "
            f"Ensure /tmp/setup_ktc.py ran successfully in the prior session."
        )

    inv = frappe.new_doc("Sales Invoice")
    inv.customer = CUSTOMER
    inv.company = COMPANY
    inv.posting_date = nowdate()
    inv.due_date = add_days(nowdate(), 30)
    inv.currency = "SAR"

    # ksa_compliance-required fields (Gotchas #1 and #2 from DECISIONS.md v0.4)
    inv.taxes_and_charges = TAX_TEMPLATE
    inv.tax_category = "Standard"

    inv.append("items", {
        "item_code": ITEM,
        "qty": 1,
        "rate": 500000,
    })

    # ERPNext will auto-populate taxes from the template during set_missing_values,
    # but we append it explicitly to be safe across environments.
    inv.append("taxes", {
        "charge_type": "On Net Total",
        "account_head": f"VAT 15% - Output - {ABBR}",
        "description": "VAT 15%",
        "rate": 15,
    })

    inv.set_missing_values()
    inv.calculate_taxes_and_totals()
    inv.insert(ignore_permissions=True)
    inv.submit()
    frappe.db.commit()
    return inv


# =============================================================================
# Helpers: GL dump + outstanding check
# =============================================================================

def dump_gl_entries(voucher_no, header):
    entries = frappe.db.sql("""
        SELECT account, debit, credit, against_voucher_type, against_voucher,
               voucher_type, voucher_no
        FROM `tabGL Entry`
        WHERE voucher_no = %s AND is_cancelled = 0
        ORDER BY account
    """, voucher_no, as_dict=True)

    print(f"\n  {header}")
    print(f"  {'Account':<45} {'Debit':>12} {'Credit':>12}  against_voucher")
    print(f"  {'-' * 45} {'-' * 12} {'-' * 12}  {'-' * 30}")
    for e in entries:
        av = e.against_voucher or "-"
        print(f"  {e.account:<45} {flt(e.debit):>12,.2f} {flt(e.credit):>12,.2f}  {av}")
    return entries


def check_outstanding(invoice_name, label):
    outstanding = frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")
    status = frappe.db.get_value("Sales Invoice", invoice_name, "status")
    print(f"  {label}")
    print(f"     outstanding_amount = {flt(outstanding):,.2f}")
    print(f"     status             = {status}")
    return flt(outstanding), status


# =============================================================================
# Step 2: Create the reclassification Journal Entry
# =============================================================================

def create_retention_je(invoice, retention_account, retention_amount):
    """
    Dr. Retention Receivable  50,000  (party-linked, reference to invoice)
        Cr. Debtors               50,000  (party-linked, reference to invoice)

    KEY: both lines carry reference_type="Sales Invoice" + reference_name.
    ERPNext uses these to tie the JE back to the invoice for outstanding calc.
    """
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = invoice.posting_date
    je.company = invoice.company
    je.user_remark = f"Retention reclassification for {invoice.name}"

    # Dr. Retention Receivable
    je.append("accounts", {
        "account": retention_account,
        "party_type": "Customer",
        "party": invoice.customer,
        "debit_in_account_currency": retention_amount,
        "credit_in_account_currency": 0,
        "reference_type": "Sales Invoice",
        "reference_name": invoice.name,
        "user_remark": f"Retention held on {invoice.name}",
    })

    # Cr. Debtors (THE CRITICAL LINE — reduces invoice receivable)
    je.append("accounts", {
        "account": invoice.debit_to,
        "party_type": "Customer",
        "party": invoice.customer,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": retention_amount,
        "reference_type": "Sales Invoice",
        "reference_name": invoice.name,
        "user_remark": f"Reclassify to Retention for {invoice.name}",
    })

    je.insert(ignore_permissions=True)
    je.submit()
    frappe.db.commit()
    return je


# =============================================================================
# Step 4: Aggregate GL balance for this invoice
# =============================================================================

def print_aggregate_gl(invoice_name):
    balance = frappe.db.sql("""
        SELECT account, SUM(debit) as debit, SUM(credit) as credit,
               SUM(debit) - SUM(credit) as balance
        FROM `tabGL Entry`
        WHERE is_cancelled = 0
          AND (
              (voucher_type = 'Sales Invoice' AND voucher_no = %(inv)s)
              OR (against_voucher_type = 'Sales Invoice' AND against_voucher = %(inv)s)
          )
        GROUP BY account
        ORDER BY account
    """, {"inv": invoice_name}, as_dict=True)

    print(f"  {'Account':<45} {'Debit':>12} {'Credit':>12} {'Balance':>14}")
    print(f"  {'-' * 45} {'-' * 12} {'-' * 12} {'-' * 14}")
    for row in balance:
        print(f"  {row.account:<45} {flt(row.debit):>12,.2f} "
              f"{flt(row.credit):>12,.2f} {flt(row.balance):>14,.2f}")


# =============================================================================
# Step 5: Attempt payment of the reduced outstanding
# =============================================================================

def attempt_payment(invoice, expected_payable):
    bank_account = frappe.db.get_value(
        "Account",
        {"company": COMPANY, "account_type": "Bank", "is_group": 0},
        "name",
    )
    if not bank_account:
        bank_account = frappe.db.get_value(
            "Account",
            {"company": COMPANY, "account_type": "Cash", "is_group": 0},
            "name",
        )

    if not bank_account:
        print("  ⚠  No Bank/Cash account found — skipping payment test")
        return None

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.party_type = "Customer"
    pe.party = invoice.customer
    pe.company = invoice.company
    pe.posting_date = nowdate()
    pe.paid_amount = expected_payable
    pe.received_amount = expected_payable
    pe.paid_from = invoice.debit_to
    pe.paid_to = bank_account

    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice.name,
        "allocated_amount": expected_payable,
    })

    try:
        pe.insert(ignore_permissions=True)
        pe.submit()
        frappe.db.commit()
        return pe
    except Exception as e:
        print(f"  ⚠  Payment Entry failed: {type(e).__name__}: {e}")
        return None


# =============================================================================
# Main flow
# =============================================================================

def main():
    frappe.set_user("Administrator")

    print("=" * 70)
    print("POC v2: Retention via Journal Entry")
    print("=" * 70)

    print("\n[Cleanup]")
    cleanup_previous_runs()

    print("\n[Setup]")
    retention_account = ensure_retention_account()

    # --- Step 1 ---
    print("\n[Step 1] Create and submit standard Sales Invoice (500k + 15% VAT)")
    inv = create_standard_invoice()
    print(f"  → Created: {inv.name}")
    print(f"     net_total   = {flt(inv.net_total):,.2f}")
    print(f"     grand_total = {flt(inv.grand_total):,.2f}")

    dump_gl_entries(inv.name, "CHECKPOINT 1: GL entries AFTER invoice submit (before JE)")
    out1, status1 = check_outstanding(inv.name, "\n  After invoice submit:")

    if abs(out1 - 575000) >= 0.01:
        print(f"  ⚠️  Expected outstanding=575,000, got {out1}. Aborting.")
        return

    print(f"  ✓ outstanding_amount = 575,000 as expected")

    # --- Step 2 ---
    print("\n[Step 2] Create reclassification JE (Dr. Retention 50k / Cr. Debtors 50k)")
    je = create_retention_je(inv, retention_account, 50000)
    print(f"  → Created: {je.name}")
    dump_gl_entries(je.name, "CHECKPOINT 2: GL entries from the Journal Entry")

    # --- Step 3: CRITICAL CHECK ---
    print("\n[Step 3] 🎯 CRITICAL CHECK — outstanding_amount AFTER JE submit")
    out2, status2 = check_outstanding(inv.name, "  After JE submit:")

    expected = 525000
    je_reduces_outstanding = False

    if abs(out2 - expected) < 0.01:
        print(f"  ✅ SUCCESS — outstanding_amount = {out2:,.2f} (expected {expected:,.2f})")
        print(f"     The hook-only design is VIABLE.")
        je_reduces_outstanding = True
    elif abs(out2 - 575000) < 0.01:
        print(f"  ❌ FAILURE — outstanding_amount = {out2:,.2f} (unchanged from 575k)")
        print(f"     ERPNext did NOT honor the reference linkage.")
        print(f"     Hook-only design needs a different approach.")
    else:
        print(f"  ⚠️  UNEXPECTED — outstanding_amount = {out2:,.2f}")
        print(f"     Delta from expected 525k: {out2 - expected:,.2f}")

    # --- Step 4 ---
    print("\n[CHECKPOINT 4] Aggregate GL balance for this invoice")
    print_aggregate_gl(inv.name)

    # --- Step 5 ---
    if je_reduces_outstanding:
        print("\n[Step 5] Attempt payment of 525,000 — should mark invoice as Paid")
        pe = attempt_payment(inv, 525000)
        if pe:
            print(f"  → Payment Entry: {pe.name}")
            out3, status3 = check_outstanding(inv.name, "\n  After payment submit:")
            if abs(out3) < 0.01 and status3 == "Paid":
                print(f"  ✅ END-TO-END SUCCESS — invoice fully paid at 525k")
                print(f"     Retention still held as separate 50k receivable.")
            else:
                print(f"  ⚠️  Payment submitted but state unexpected")
                print(f"     outstanding={out3}, status={status3}")
    else:
        print("\n[Step 5] Skipped — Step 3 must pass first")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("POC SUMMARY")
    print("=" * 70)
    print(f"  Invoice: {inv.name}")
    print(f"  Journal Entry: {je.name}")
    print(f"  outstanding_amount after JE: {out2:,.2f} (expected 525,000.00)")
    verdict = "✅ Hook-only VIABLE" if je_reduces_outstanding else "❌ Hook-only NOT viable"
    print(f"  Verdict: {verdict}")
    print("=" * 70)


main()
