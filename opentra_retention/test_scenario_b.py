"""
Scenario B: Mixed partial payments deep test (two-account retention flow).

Flow:
  SI submit       → Holdback JV: DR 1311 | CR Debtors
  RR submit       → Transfer JV: DR 1312 | CR 1311  (SI outstanding unchanged)
  Create PE       → Transfer JV: DR Debtors [ref SI] | CR 1312  (SI outstanding +release_amount)
                  → PE draft created
  PE submit       → DR Cash | CR Debtors  (SI outstanding -release_amount, net: unchanged)

Run via:
  bench --site test2.opentra.opentech.sa execute opentra_retention.test_scenario_b.execute
"""

import frappe
from frappe.utils import flt, today

COMPANY        = "DemoCompany"
CUSTOMER       = "Test 0"
COST_CENTER    = "Main - D"
AR_ACCOUNT     = "1310 - Debtors - D"
RET_ACCOUNT    = "1311 - Retention Receivable - D"
REL_ACCOUNT    = "1312 - Retention Released Receivable - D"
CASH_ACCOUNT   = "1110 - Cash - D"
VAT_ACCOUNT    = "2311 - VAT 15% - Output - D"

OK  = "✅"
BAD = "❌"

_failures = []


def _check(label, actual, expected, tol=0.01):
    ok = abs(flt(actual) - flt(expected)) <= tol
    sym = OK if ok else BAD
    print(f"  {sym} {label}: {actual} (expected {expected})")
    if not ok:
        _failures.append(f"{label}: got {actual}, expected {expected}")
    return ok


def _si_outstanding(si_name):
    return flt(frappe.db.get_value("Sales Invoice", si_name, "outstanding_amount"))


def _si_status(si_name):
    return frappe.db.get_value("Sales Invoice", si_name, "status")


def _rr_status(rr_name):
    return frappe.db.get_value("Retention Release", rr_name, "status")


def _check_status(label, actual, expected):
    ok = actual == expected
    print(f"  {OK if ok else BAD} {label}: {actual} (expected {expected})")
    if not ok:
        _failures.append(f"{label}: got {actual!r}, expected {expected!r}")
    return ok


def _ret_receivable_balance(vouchers):
    """Net debit-credit on Retention Receivable, scoped to the given voucher names only."""
    if not vouchers:
        return 0.0
    rows = frappe.db.sql(
        "SELECT SUM(debit - credit) as bal FROM `tabGL Entry`"
        " WHERE account=%s AND voucher_no IN %s AND is_cancelled=0",
        (RET_ACCOUNT, tuple(vouchers)),
        as_dict=True,
    )
    return flt(rows[0].bal) if rows else 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Document creation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_si():
    """Item 001 × 500,000 + 15 % VAT, 10 % retention."""
    si = frappe.new_doc("Sales Invoice")
    si.company      = COMPANY
    si.customer     = CUSTOMER
    si.posting_date = today()
    si.due_date     = today()
    si.custom_retention_percentage = "10%"
    si.append("items", {
        "item_code":    "Item 001",
        "qty":          1,
        "rate":         500000,
        "cost_center":  COST_CENTER,
    })
    si.append("taxes", {
        "charge_type":  "On Net Total",
        "account_head": VAT_ACCOUNT,
        "rate":         15,
        "description":  "VAT 15%",
    })
    si.flags.ignore_permissions = True
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()
    return si.name


def _create_normal_pe(si_name, amount):
    """Standard Payment Entry referencing the SI."""
    outstanding = _si_outstanding(si_name)
    grand_total  = flt(frappe.db.get_value("Sales Invoice", si_name, "grand_total"))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type              = "Receive"
    pe.company                   = COMPANY
    pe.posting_date              = today()
    pe.party_type                = "Customer"
    pe.party                     = CUSTOMER
    pe.paid_from                 = AR_ACCOUNT
    pe.paid_from_account_type    = "Receivable"
    pe.paid_from_account_currency = "SAR"
    pe.paid_to                   = CASH_ACCOUNT
    pe.paid_to_account_currency  = "SAR"
    pe.source_exchange_rate      = 1
    pe.target_exchange_rate      = 1
    pe.paid_amount               = amount
    pe.received_amount           = amount
    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name":    si_name,
        "allocated_amount":  amount,
        "outstanding_amount": outstanding,
        "total_amount":      grand_total,
    })
    pe.remarks = f"Test payment {amount:,.0f} for {si_name}"
    pe.flags.ignore_permissions = True
    pe.insert(ignore_permissions=True)
    pe.submit()
    frappe.db.commit()
    return pe.name


def _create_retention_release(si_name, amount):
    """Create and submit a Retention Release."""
    rr = frappe.new_doc("Retention Release")
    rr.sales_invoice  = si_name
    rr.release_date   = today()
    rr.release_amount = amount
    rr.flags.ignore_permissions = True
    rr.insert(ignore_permissions=True)
    rr.submit()
    frappe.db.commit()
    return rr.name


def _create_retention_pe(rr_name):
    """
    Create Transfer JV + PE via api.make_retention_payment_entry(), then submit the PE.
    Transfer JV (DR Debtors [ref SI] | CR 1312) is submitted inside the API call.
    """
    import opentra_retention.api as api
    result = api.make_retention_payment_entry(rr_name)
    if not result.get("success"):
        raise Exception(f"make_retention_payment_entry failed: {result}")
    pe_name = result["data"]["name"]
    pe_doc  = frappe.get_doc("Payment Entry", pe_name)
    pe_doc.flags.ignore_permissions = True
    pe_doc.submit()
    frappe.db.commit()
    return pe_name


# ─────────────────────────────────────────────────────────────────────────────
#  Main test
# ─────────────────────────────────────────────────────────────────────────────

def execute():
    _failures.clear()
    print("=" * 65)
    print("SCENARIO B — Mixed Partial Payments Deep Test")
    print("=" * 65)

    # ── SETUP ────────────────────────────────────────────────────────────────
    print("\n── SETUP: Create Sales Invoice ──")
    si_name = _create_si()
    print(f"  SI: {si_name}")

    # Reload to pick up hook-set fields (custom_retention_jv, custom_retention_amount)
    si = frappe.get_doc("Sales Invoice", si_name)
    _check("Grand Total",         si.grand_total,          575000)
    _check("Retention Amount",    si.custom_retention_amount, 50000)

    ret_jv = si.custom_retention_jv
    if ret_jv:
        print(f"  {OK} Retention JV: {ret_jv}")
    else:
        print(f"  {BAD} Retention JV NOT set")
        _failures.append("Retention JV not created on SI submit")

    _check("SI Outstanding after submit", _si_outstanding(si_name), 525000)

    # ── STEP 1: Pay 200,000 ──────────────────────────────────────────────────
    print("\n── STEP 1: Normal PE — 200,000 ──")
    pe1 = _create_normal_pe(si_name, 200000)
    print(f"  PE: {pe1}")
    _check("SI Outstanding", _si_outstanding(si_name), 325000)
    _check_status("SI Status", _si_status(si_name), "Partly Paid")

    # ── STEP 2: Retention Release 15,000 ─────────────────────────────────────
    print("\n── STEP 2: Retention Release — 15,000 ──")
    rr1 = _create_retention_release(si_name, 15000)
    print(f"  RR: {rr1}")
    rr1_doc = frappe.get_doc("Retention Release", rr1)

    if rr1_doc.release_jv:
        print(f"  {OK} Release JV (1312←1311): {rr1_doc.release_jv}")
    else:
        print(f"  {BAD} Release JV NOT created")
        _failures.append("RR1: Release JV not created")

    # SI outstanding unchanged — Transfer JV only moves 1311→1312, no Debtors change
    _check("SI Outstanding (unchanged at 325k)", _si_outstanding(si_name), 325000)
    _check("1311 balance (50k − 15k = 35k)", _ret_receivable_balance([ret_jv, rr1_doc.release_jv]), 35000)

    # ── STEP 3: Pay retention 15,000 ─────────────────────────────────────────
    print("\n── STEP 3: Retention PE — 15,000 ──")
    pe2 = _create_retention_pe(rr1)
    print(f"  PE: {pe2}")
    # Transfer JV added 15k to SI outstanding; PE reduced it by 15k → net unchanged
    _check("SI Outstanding (net unchanged at 325k)", _si_outstanding(si_name), 325000)
    _check_status("RR1 Status", _rr_status(rr1), "Paid")

    # ── STEP 4: Pay 200,000 ──────────────────────────────────────────────────
    print("\n── STEP 4: Normal PE — 200,000 ──")
    pe3 = _create_normal_pe(si_name, 200000)
    print(f"  PE: {pe3}")
    _check("SI Outstanding (325k − 200k)", _si_outstanding(si_name), 125000)

    # ── STEP 5: Retention Release 35,000 ─────────────────────────────────────
    print("\n── STEP 5: Retention Release — 35,000 (remainder) ──")
    rr2 = _create_retention_release(si_name, 35000)
    print(f"  RR: {rr2}")
    rr2_doc = frappe.get_doc("Retention Release", rr2)

    if rr2_doc.release_jv:
        print(f"  {OK} Release JV (1312←1311): {rr2_doc.release_jv}")
    else:
        print(f"  {BAD} Release JV NOT created")
        _failures.append("RR2: Release JV not created")

    # SI outstanding unchanged — Transfer JV only moves 1311→1312
    _check("SI Outstanding (unchanged at 125k)", _si_outstanding(si_name), 125000)
    _check("1311 balance (35k − 35k = 0)", _ret_receivable_balance([ret_jv, rr1_doc.release_jv, rr2_doc.release_jv]), 0)

    # ── STEP 6: Pay retention 35,000 ─────────────────────────────────────────
    print("\n── STEP 6: Retention PE — 35,000 ──")
    pe4 = _create_retention_pe(rr2)
    print(f"  PE: {pe4}")
    # Transfer JV added 35k; PE reduced it by 35k → net unchanged
    _check("SI Outstanding (net unchanged at 125k)", _si_outstanding(si_name), 125000)
    _check_status("RR2 Status", _rr_status(rr2), "Paid")

    # ── STEP 7: Final payment 125,000 ────────────────────────────────────────
    print("\n── STEP 7: Final PE — 125,000 ──")
    pe5 = _create_normal_pe(si_name, 125000)
    print(f"  PE: {pe5}")
    _check("SI Outstanding (final)",  _si_outstanding(si_name), 0)
    _check_status("SI Final Status", _si_status(si_name), "Paid")

    # ── FINAL GL VERIFICATION ────────────────────────────────────────────────
    print("\n── FINAL GL VERIFICATION (all vouchers) ──")
    # Reload RR docs to pick up payment_transfer_jv set by make_retention_payment_entry
    rr1_doc.reload()
    rr2_doc.reload()
    all_vouchers = [
        si_name,
        ret_jv or "__none__",
        rr1_doc.release_jv or "__none__",
        rr2_doc.release_jv or "__none__",
        rr1_doc.payment_transfer_jv or "__none__",
        rr2_doc.payment_transfer_jv or "__none__",
        pe1, pe2, pe3, pe4, pe5,
    ]

    gl = frappe.db.sql("""
        SELECT
            account,
            SUM(debit)          AS total_dr,
            SUM(credit)         AS total_cr,
            SUM(debit - credit) AS balance
        FROM `tabGL Entry`
        WHERE voucher_no IN %(vouchers)s
          AND is_cancelled = 0
        GROUP BY account
        ORDER BY account
    """, {"vouchers": all_vouchers}, as_dict=True)

    print(f"  {'Account':<45} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
    print(f"  {'-'*45} {'-'*12} {'-'*12} {'-'*12}")
    for row in gl:
        print(f"  {row.account:<45} {row.total_dr:>12,.0f} {row.total_cr:>12,.0f} {row.balance:>12,.0f}")

    print()
    for row in gl:
        if row.account == AR_ACCOUNT:
            _check("Debtors final balance = 0", row.balance, 0)
        elif row.account == RET_ACCOUNT:
            _check("Retention Receivable final balance = 0", row.balance, 0)
        elif row.account == CASH_ACCOUNT:
            _check("Cash total received = 575,000", row.balance, 575000)

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    if not _failures:
        print(f"{OK} ALL CHECKS PASSED — Scenario B complete")
    else:
        print(f"{BAD} {len(_failures)} CHECK(S) FAILED:")
        for f in _failures:
            print(f"    • {f}")
    print()
    print(f"  SI  : {si_name}")
    print(f"  RR1 : {rr1}  ({_rr_status(rr1)})  release_jv={rr1_doc.release_jv}  transfer_jv={rr1_doc.payment_transfer_jv}")
    print(f"  RR2 : {rr2}  ({_rr_status(rr2)})  release_jv={rr2_doc.release_jv}  transfer_jv={rr2_doc.payment_transfer_jv}")
    print(f"  PEs : {pe1}, {pe2}, {pe3}, {pe4}, {pe5}")
    print("=" * 65)
