"""
POC: Retention via Journal Entry (Hook-only approach)
=====================================================

PURPOSE:
    Validate the critical assumption that underpins the hook-only design:

    "A Journal Entry crediting Debtors with against_voucher=<invoice_name>
     will be recognized by ERPNext as reducing the invoice's
     outstanding_amount — without any code override."

    If this holds, we can build the entire retention feature using only
    doc_events hooks (zero core override).

    If this fails, we need to reconsider the approach.

SCENARIO:
    Follows the spec document example:
        Net total         = 500,000
        VAT 15%           =  75,000
        Grand total       = 575,000
        Retention (10%)   =  50,000  (on net, no VAT)

    Expected final state after this POC:
        Sales Invoice GL:
            Dr. Debtors                 575,000
                Cr. Sales                   500,000
                Cr. VAT Output 15%           75,000
        Journal Entry GL (auto-created here):
            Dr. Retention Receivable     50,000
                Cr. Debtors                  50,000
        Combined ledger on this invoice:
            Debtors net                 525,000  ← what ERPNext should see
            Retention Receivable         50,000

    CRITICAL CHECK — outstanding_amount on the invoice should be 525,000
    (not 575,000) after the JE submits.

USAGE on Customer Server:
    # 1. Upload this file to /tmp/
    sudo chown frappe:frappe /tmp/poc_retention_je.py

    # 2. Run in bench console
    sudo -iu frappe bash -c "cd /home/frappe/frappe-bench && \
        bench --site ksatest.opentra.opentech.sa console" <<'STDIN'
    exec(open('/tmp/poc_retention_je.py').read())
    exit()
    STDIN

RESULTS TO REPORT BACK:
    The script prints 5 numbered checkpoints. Send me the full output,
    especially CHECKPOINT 3 (outstanding_amount after JE) — this is the
    make-or-break data point.
"""

import frappe
from frappe.utils import flt, nowdate, add_days

COMPANY = "KSA Test Company"
ABBR = "KTC"
CUSTOMER = "Test B2B Customer"
ITEM = "TEST-ITEM-01"


# -----------------------------------------------------------------------------
# Setup: ensure Retention account exists (as Receivable type for now)
# -----------------------------------------------------------------------------

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
    acc.account_type = "Receivable"  # POC uses standard Receivable; production will use Receivable Retention
    acc.account_currency = "SAR"
    acc.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  → Created: {acc.name}")
    return acc.name


# -----------------------------------------------------------------------------
# Step 1: Create and submit a standard Sales Invoice (no retention customization)
# -----------------------------------------------------------------------------

def create_standard_invoice():
    inv = frappe.new_doc("Sales Invoice")
    inv.customer = CUSTOMER
    inv.company = COMPANY
    inv.posting_date = nowdate()
    inv.due_date = add_days(nowdate(), 30)
    inv.currency = "SAR"

    inv.append("items", {
        "item_code": ITEM,
        "qty": 1,
        "rate": 500000,
    })

    inv.append("taxes", {
        "charge_type": "On Net Total",
        "account_head": f"VAT 15% - Output - {ABBR}",
        "description": "VAT 15%",
        "rate": 15,
    })

    inv.insert(ignore_permissions=True)
    inv.submit()
    frappe.db.commit()
    return inv


def dump_gl_entries(voucher_no, header):
    entries = frappe.db.sql("""
        SELECT account, debit, credit, against_voucher_type, against_voucher, voucher_type, voucher_no
        FROM `tabGL Entry`
        WHERE voucher_no = %s AND is_cancelled = 0
        ORDER BY account
    """, voucher_no, as_dict=True)

    print(f"\n  {header}")
    print(f"  {'Account':<45} {'Debit':>12} {'Credit':>12}  voucher")
    print(f"  {'-' * 45} {'-' * 12} {'-' * 12}  {'-' * 30}")
    for e in entries:
        v = f"{e.voucher_type or '?'}/{e.voucher_no or '?'}"
        print(f"  {e.account:<45} {flt(e.debit):>12,.2f} {flt(e.credit):>12,.2f}  {v}")
    return entries


# -----------------------------------------------------------------------------
# Step 2: Create the reclassification Journal Entry
# -----------------------------------------------------------------------------

def create_retention_je(invoice, retention_account, retention_amount):
    """
    Auto-create a Journal Entry that reclassifies part of the receivable:
        Dr. Retention Receivable      <retention_amount>
            Cr. Debtors                   <retention_amount>

    KEY DESIGN CHOICE: The Cr. Debtors line carries against_voucher_type
    and against_voucher pointing to the original Sales Invoice. This is
    the lever we're testing — whether ERPNext honors this linkage when
    computing outstanding_amount.
    """
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = invoice.posting_date
    je.company = invoice.company
    je.user_remark = f"Retention reclassification for {invoice.name}"

    # Dr. Retention Receivable (party-linked)
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

    # Cr. Debtors (THIS IS THE CRITICAL LINE — against_voucher links it to the invoice)
    je.append("accounts", {
        "account": invoice.debit_to,
        "party_type": "Customer",
        "party": invoice.customer,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": retention_amount,
        "reference_type": "Sales Invoice",
        "reference_name": invoice.name,
        "user_remark": f"Reclassify to Retention account for {invoice.name}",
    })

    je.insert(ignore_permissions=True)
    je.submit()
    frappe.db.commit()
    return je


# -----------------------------------------------------------------------------
# Step 3: Verify outstanding_amount behavior
# -----------------------------------------------------------------------------

def check_outstanding(invoice_name, label):
    """Read outstanding_amount fresh from DB (not cached doc)."""
    outstanding = frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")
    status = frappe.db.get_value("Sales Invoice", invoice_name, "status")
    print(f"  {label}")
    print(f"     outstanding_amount = {flt(outstanding):,.2f}")
    print(f"     status             = {status}")
    return flt(outstanding), status


# -----------------------------------------------------------------------------
# Step 4: Try to pay the reduced outstanding via Payment Entry
# -----------------------------------------------------------------------------

def attempt_payment(invoice, expected_payable):
    """
    Create a Payment Entry for expected_payable (525k) against this invoice.
    If the invoice becomes status='Paid' after submit, we've confirmed the
    entire design works end-to-end.
    """
    bank_account = frappe.db.get_value(
        "Account",
        {"company": COMPANY, "account_type": "Bank", "is_group": 0},
        "name",
    )
    if not bank_account:
        # Fallback: find any Cash account
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


# -----------------------------------------------------------------------------
# Main POC flow
# -----------------------------------------------------------------------------

def main():
    frappe.set_user("Administrator")

    print("=" * 70)
    print("POC: Retention via Journal Entry")
    print("=" * 70)

    # --- Setup ---
    print("\n[Setup]")
    retention_account = ensure_retention_account()

    # --- Step 1: Create standard invoice ---
    print("\n[Step 1] Create and submit a standard Sales Invoice (500k + 15% VAT)")
    inv = create_standard_invoice()
    print(f"  → Created: {inv.name}")
    print(f"     net_total      = {flt(inv.net_total):,.2f}")
    print(f"     grand_total    = {flt(inv.grand_total):,.2f}")
    dump_gl_entries(inv.name, "CHECKPOINT 1: GL entries AFTER invoice submit (before JE)")

    out1, status1 = check_outstanding(inv.name, "\n  After invoice submit:")
    assert abs(out1 - 575000) < 0.01, f"Expected 575,000, got {out1}"
    print(f"  ✓ outstanding_amount = 575,000 as expected")

    # --- Step 2: Create the reclassification JE ---
    print("\n[Step 2] Create reclassification Journal Entry (Dr. Retention / Cr. Debtors 50k)")
    je = create_retention_je(inv, retention_account, 50000)
    print(f"  → Created: {je.name}")
    dump_gl_entries(je.name, "CHECKPOINT 2: GL entries from the Journal Entry")

    # --- Step 3: CRITICAL CHECK — outstanding_amount after JE ---
    print("\n[Step 3] 🎯 CRITICAL CHECK — outstanding_amount AFTER Journal Entry submit")
    out2, status2 = check_outstanding(inv.name, "  After JE submit:")

    expected = 525000
    delta = out2 - expected

    if abs(delta) < 0.01:
        print(f"  ✅ SUCCESS — outstanding_amount = {out2:,.2f} (expected {expected:,.2f})")
        print(f"     The hook-only design is VIABLE.")
        je_reduces_outstanding = True
    elif abs(out2 - 575000) < 0.01:
        print(f"  ❌ FAILURE — outstanding_amount = {out2:,.2f} (unchanged from 575k)")
        print(f"     ERPNext did NOT honor the against_voucher linkage.")
        print(f"     Hook-only design NOT viable. Need a different approach.")
        je_reduces_outstanding = False
    else:
        print(f"  ⚠️  UNEXPECTED — outstanding_amount = {out2:,.2f}")
        print(f"     Delta from expected 525k: {delta:,.2f}")
        print(f"     Investigate manually.")
        je_reduces_outstanding = False

    # --- Step 4: Aggregate GL view ---
    print("\n[CHECKPOINT 4] Aggregate GL balance for this customer on this invoice")
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
    """, {"inv": inv.name}, as_dict=True)

    print(f"  {'Account':<45} {'Debit':>12} {'Credit':>12} {'Balance':>14}")
    print(f"  {'-' * 45} {'-' * 12} {'-' * 12} {'-' * 14}")
    for row in balance:
        print(f"  {row.account:<45} {flt(row.debit):>12,.2f} "
              f"{flt(row.credit):>12,.2f} {flt(row.balance):>14,.2f}")

    # --- Step 5: Payment Entry test (only if Step 3 passed) ---
    if je_reduces_outstanding:
        print("\n[Step 5] Attempt payment of 525,000 — should mark invoice as Paid")
        pe = attempt_payment(inv, 525000)
        if pe:
            print(f"  → Payment Entry: {pe.name}")
            out3, status3 = check_outstanding(inv.name, "\n  After payment submit:")
            if abs(out3) < 0.01 and status3 == "Paid":
                print(f"  ✅ END-TO-END SUCCESS")
                print(f"     Invoice is fully paid at 525k, retention still held as 50k.")
            else:
                print(f"  ⚠️  Payment completed but invoice state unexpected")
                print(f"     outstanding={out3}, status={status3}")
    else:
        print("\n[Step 5] Skipped — Step 3 failed, no point testing payment")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("POC SUMMARY")
    print("=" * 70)
    print(f"  Invoice: {inv.name}")
    print(f"  Journal Entry: {je.name if je else 'N/A'}")
    print(f"  outstanding_amount after JE: {out2:,.2f} (expected 525,000)")
    print(f"  Verdict: {'✅ Hook-only design VIABLE' if je_reduces_outstanding else '❌ Hook-only NOT viable'}")
    print("=" * 70)


main()
