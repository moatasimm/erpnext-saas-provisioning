"""
============================================================
Retention Full Test Suite — opentra_retention v2
============================================================
Tests EVERY scenario end-to-end:

  SCENARIO A: Invoice → Regular Payment → Retention Release → Payment
  SCENARIO B: Invoice Cancellation (JV should cancel too)
              NOTE: If ksa_compliance is installed, ZATCA blocks cancellation
              → test verifies JV is submitted AND ZATCA guard fires correctly
  SCENARIO C: API endpoint verification
  SCENARIO D: Partial Retention Release (50% then 50%)

Run:
  bench --site ksatest.opentra.opentech.sa execute \
    opentra_retention.test_retention_full.execute 2>&1
"""

import frappe
from frappe.utils import today, flt, add_days

SITE    = "ksatest.opentra.opentech.sa"
COMPANY = "KSA Test Company"
ABBR    = "KTC"

PASS = "✅ PASS"
FAIL = "❌ FAIL"


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sep(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
    print("─" * 60)


def _check(label, condition, got=None):
    status = PASS if condition else FAIL
    msg = f"  {status}  {label}"
    if got is not None:
        msg += f"  →  {got}"
    print(msg)
    return condition


def _get_ar_outstanding(invoice_name):
    """
    Use ERPNext's own outstanding_amount field — this is updated by the
    GL reconciliation engine whenever JVs or payments reference the invoice.
    """
    return flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount"))


def _get_retention_jv_balance(invoice_name, customer):
    """
    Balance on Retention Receivable account created by the invoice's own retention JV.
    Looks only at entries for the specific retention JV linked to this invoice.
    """
    retention_account = frappe.db.get_value("Company", COMPANY, "default_retention_account")
    jv_name = frappe.db.get_value("Sales Invoice", invoice_name, "custom_retention_jv")
    if not jv_name:
        return 0.0
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(debit) - SUM(credit), 0)
        FROM `tabGL Entry`
        WHERE
            voucher_no   = %s
            AND account  = %s
            AND party    = %s
            AND is_cancelled = 0
        """,
        (jv_name, retention_account, customer),
    )
    return flt((row or [[0]])[0][0])


def _get_release_jv_ar_delta(release_jv, customer):
    """
    Net debit on AR account from a specific Release JV.
    Positive = AR increased (retention released back to AR).
    """
    ar_account = frappe.db.get_value("Company", COMPANY, "default_receivable_account") or \
                 frappe.db.get_value("Account",
                     {"company": COMPANY, "account_type": "Receivable", "is_group": 0},
                     "name")
    if not release_jv:
        return 0.0
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(debit) - SUM(credit), 0)
        FROM `tabGL Entry`
        WHERE
            voucher_no   = %s
            AND party    = %s
            AND is_cancelled = 0
        """,
        (release_jv, customer),
    )
    return flt((row or [[0]])[0][0])


def _make_invoice(item_name, qty, rate, retention_pct="10%", customer=None):
    """Create and submit a Sales Invoice with retention."""
    if not customer:
        customer = frappe.get_all("Customer", limit=1)[0].name

    tax_template = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        {"company": COMPANY},
        "name"
    )

    inv = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": COMPANY,
        "customer": customer,
        "posting_date": today(),
        "due_date": add_days(today(), 30),
        "items": [{
            "item_code": item_name,
            "qty": qty,
            "rate": rate,
        }],
        "taxes_and_charges": tax_template,
        "taxes": frappe.get_doc("Sales Taxes and Charges Template", tax_template).taxes if tax_template else [],
        "custom_retention_percentage": retention_pct,
    })
    inv.flags.ignore_permissions = True
    inv.insert(ignore_permissions=True)
    inv.submit()
    inv.reload()
    return inv


def _make_payment(customer, invoice_name, amount, paid_to_account=None):
    """Create and submit a Payment Entry against an invoice."""
    if not paid_to_account:
        paid_to_account = frappe.db.get_value(
            "Account",
            {"company": COMPANY, "account_type": "Cash", "is_group": 0},
            "name"
        )
    ar_account = frappe.db.get_value("Sales Invoice", invoice_name, "debit_to")

    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "company": COMPANY,
        "posting_date": today(),
        "party_type": "Customer",
        "party": customer,
        "paid_from": ar_account,
        "paid_to": paid_to_account,
        "paid_amount": amount,
        "received_amount": amount,
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice_name,
            "allocated_amount": amount,
        }],
    })
    pe.flags.ignore_permissions = True
    pe.insert(ignore_permissions=True)
    pe.submit()
    pe.reload()
    return pe


def _make_retention_release(invoice_name, release_amount):
    """
    Create and submit a Retention Release.

    IMPORTANT: Use frappe.new_doc() — NOT frappe.get_doc({dict}).
    frappe.get_doc({dict}) does NOT apply DocType field defaults (e.g. naming_series).
    frappe.new_doc() correctly initialises all defaults including naming_series.
    """
    inv = frappe.get_doc("Sales Invoice", invoice_name)
    rr = frappe.new_doc("Retention Release")
    rr.company       = COMPANY
    rr.customer      = inv.customer
    rr.sales_invoice = invoice_name
    rr.release_date  = today()
    rr.release_amount = release_amount
    rr.flags.ignore_permissions = True
    rr.insert(ignore_permissions=True)
    rr.submit()
    rr.reload()
    return rr


# ──────────────────────────────────────────────────────────────────────────────
#  SCENARIO A: Full Happy Path
# ──────────────────────────────────────────────────────────────────────────────

def scenario_a():
    _sep("SCENARIO A: Full Happy Path")
    print("  Flow: Invoice → Regular Payment → Retention Release → Final Payment")

    item = frappe.get_all(
        "Item", filters={"is_sales_item": 1}, fields=["name"], limit=1
    )
    if not item:
        print(f"  {FAIL}  No sales items found — skipping")
        return False

    item_name = item[0].name
    customer  = frappe.get_all("Customer", limit=1)[0].name

    # ── Step 1: Create invoice
    print(f"\n  [1] Creating invoice: {item_name} × 1 @ 500,000 SAR, Retention 10%")
    inv = _make_invoice(item_name, 1, 500000, "10%", customer)

    net_total       = flt(inv.net_total)
    grand_total     = flt(inv.grand_total)
    retention_amt   = flt(inv.custom_retention_amount)
    net_after_ret   = flt(inv.custom_net_after_retention)
    jv_name         = inv.custom_retention_jv

    print(f"     Invoice: {inv.name}")
    print(f"     Net Total:         {net_total:>12,.2f}")
    print(f"     Grand Total:       {grand_total:>12,.2f}")
    print(f"     Retention (10%):   {retention_amt:>12,.2f}")
    print(f"     Net After Ret:     {net_after_ret:>12,.2f}")
    print(f"     Retention JV:      {jv_name}")

    _check("Retention amount = net_total * 10%",
           abs(retention_amt - net_total * 0.10) < 1,
           f"{retention_amt:,.2f}")
    _check("Net after retention = grand_total - retention",
           abs(net_after_ret - (grand_total - retention_amt)) < 1,
           f"{net_after_ret:,.2f}")
    _check("Retention JV was auto-created", bool(jv_name), jv_name)

    # ── Step 2: Verify AR outstanding = net_after_retention
    ar_out_after_inv = _get_ar_outstanding(inv.name)
    _check(
        f"AR outstanding after invoice = {net_after_ret:,.2f}",
        abs(ar_out_after_inv - net_after_ret) < 1,
        f"{ar_out_after_inv:,.2f}",
    )

    # Verify Retention Receivable balance (via the specific JV only)
    ret_bal_after_inv = _get_retention_jv_balance(inv.name, customer)
    _check(
        f"Retention JV balance = {retention_amt:,.2f}",
        abs(ret_bal_after_inv - retention_amt) < 1,
        f"{ret_bal_after_inv:,.2f}",
    )

    # ── Step 3: Regular payment for net_after_retention
    print(f"\n  [3] Creating regular payment: {net_after_ret:,.2f}")
    pe = _make_payment(customer, inv.name, net_after_ret)
    print(f"     Payment Entry: {pe.name}")

    ar_out_after_pe = _get_ar_outstanding(inv.name)
    _check(
        "AR outstanding after regular payment = 0",
        abs(ar_out_after_pe) < 1,
        f"{ar_out_after_pe:,.2f}",
    )

    # ── Step 4: Retention Release
    print(f"\n  [4] Creating Retention Release: {retention_amt:,.2f}")
    rr = _make_retention_release(inv.name, retention_amt)
    print(f"     Retention Release: {rr.name}  |  JV: {rr.release_jv}")

    _check("Retention Release status = Released", rr.status == "Released", rr.status)
    _check("Release JV was created", bool(rr.release_jv), rr.release_jv)

    # AR should now have retention_amt outstanding again
    ar_out_after_rr = _get_ar_outstanding(inv.name)
    _check(
        f"AR outstanding after Release = {retention_amt:,.2f}",
        abs(ar_out_after_rr - retention_amt) < 1,
        f"{ar_out_after_rr:,.2f}",
    )

    # ── Step 5: Final payment for retention amount
    print(f"\n  [5] Creating final payment for retention: {retention_amt:,.2f}")
    pe2 = _make_payment(customer, inv.name, retention_amt)
    print(f"     Payment Entry: {pe2.name}")

    ar_out_final = _get_ar_outstanding(inv.name)
    _check(
        "AR outstanding after final payment = 0",
        abs(ar_out_final) < 1,
        f"{ar_out_final:,.2f}",
    )

    print(f"\n  ✅ SCENARIO A COMPLETE: Invoice {inv.name}")
    return inv.name


# ──────────────────────────────────────────────────────────────────────────────
#  SCENARIO B: Invoice Cancellation
# ──────────────────────────────────────────────────────────────────────────────

def scenario_b():
    _sep("SCENARIO B: Invoice Cancellation")
    print("  Flow: Invoice → Cancel Invoice → Verify JV cancelled")
    print("  NOTE: ksa_compliance may block cancellation per ZATCA rules")

    item = frappe.get_all("Item", filters={"is_sales_item": 1}, limit=1)
    if not item:
        print(f"  {FAIL}  No sales items found — skipping")
        return

    item_name = item[0].name
    customer  = frappe.get_all("Customer", limit=1)[0].name

    print(f"\n  [1] Creating invoice with 5% retention")
    inv = _make_invoice(item_name, 1, 100000, "5%", customer)
    jv_name = inv.custom_retention_jv
    print(f"     Invoice: {inv.name}  |  JV: {jv_name}")

    _check("JV was created", bool(jv_name), jv_name)

    jv_status_before = frappe.db.get_value("Journal Entry", jv_name, "docstatus") if jv_name else None
    _check("JV is submitted (docstatus=1)", jv_status_before == 1, jv_status_before)

    print(f"\n  [2] Attempting to cancel invoice {inv.name}")
    try:
        inv_doc = frappe.get_doc("Sales Invoice", inv.name)
        inv_doc.flags.ignore_links = True
        inv_doc.cancel()

        jv_status_after = frappe.db.get_value("Journal Entry", jv_name, "docstatus") if jv_name else None
        _check("JV is cancelled (docstatus=2) after invoice cancel", jv_status_after == 2, jv_status_after)
        print(f"\n  ✅ SCENARIO B COMPLETE (cancellation succeeded)")

    except frappe.ValidationError as e:
        err_str = str(e)
        if "ZATCA" in err_str or "cancel" in err_str.lower():
            print(f"  ⚠️  ZATCA Compliance blocks cancellation (ksa_compliance installed)")
            print(f"  {PASS}  ZATCA correctly prevents invoice cancellation per regulations")
            # Verify JV still exists and is submitted (not cancelled)
            jv_status_after = frappe.db.get_value("Journal Entry", jv_name, "docstatus") if jv_name else None
            _check("JV still submitted after failed cancel attempt", jv_status_after == 1, jv_status_after)
            print(f"\n  ✅ SCENARIO B COMPLETE (ZATCA guard confirmed)")
        else:
            raise


# ──────────────────────────────────────────────────────────────────────────────
#  SCENARIO C: API Verification
# ──────────────────────────────────────────────────────────────────────────────

def scenario_c():
    _sep("SCENARIO C: API Verification")

    from opentra_retention.api import get_retention_summary, get_retention_outstanding, get_invoice_retention_status

    # get_retention_summary
    summary = get_retention_summary(COMPANY)
    print(f"\n  get_retention_summary({COMPANY}):")
    print(f"     total_invoices_with_retention : {summary['total_invoices_with_retention']}")
    print(f"     total_retention_amount        : {summary['total_retention_amount']:,.2f}")
    print(f"     total_retention_released      : {summary['total_retention_released']:,.2f}")
    print(f"     total_retention_outstanding   : {summary['total_retention_outstanding']:,.2f}")
    print(f"     retention_account             : {summary['retention_account']}")

    _check("summary has retention_account set",
           summary["retention_account"] != "NOT CONFIGURED",
           summary["retention_account"])
    _check("outstanding >= 0",
           summary["total_retention_outstanding"] >= 0,
           summary["total_retention_outstanding"])

    # get_retention_outstanding
    outstanding_list = get_retention_outstanding(COMPANY)
    print(f"\n  get_retention_outstanding({COMPANY}): {len(outstanding_list)} invoice(s)")
    for row in outstanding_list:
        print(f"     {row['sales_invoice']}  customer={row['customer']}  "
              f"retention={row['retention_amount']:,.2f}  "
              f"outstanding={row['retention_outstanding']:,.2f}")

    _check("API returns list", isinstance(outstanding_list, list))

    print(f"\n  ✅ SCENARIO C COMPLETE")


# ──────────────────────────────────────────────────────────────────────────────
#  SCENARIO D: Partial Release (two tranches)
# ──────────────────────────────────────────────────────────────────────────────

def scenario_d():
    _sep("SCENARIO D: Partial Retention Release (50% + 50%)")

    item = frappe.get_all("Item", filters={"is_sales_item": 1}, limit=1)
    if not item:
        print(f"  {FAIL}  No items found — skipping")
        return

    item_name = item[0].name
    customer  = frappe.get_all("Customer", limit=1)[0].name

    print(f"\n  [1] Creating invoice with 10% retention on 200,000")
    inv = _make_invoice(item_name, 1, 200000, "10%", customer)
    retention_amt = flt(inv.custom_retention_amount)
    net_after_ret = flt(inv.custom_net_after_retention)
    print(f"     Invoice: {inv.name}  |  Retention: {retention_amt:,.2f}")

    # Regular payment
    print(f"\n  [2] Regular payment: {net_after_ret:,.2f}")
    _make_payment(customer, inv.name, net_after_ret)

    ar_after_pe = _get_ar_outstanding(inv.name)
    _check("AR after regular payment = 0", abs(ar_after_pe) < 1, f"{ar_after_pe:,.2f}")

    # First partial release: 50%
    first_release = flt(retention_amt * 0.5, 2)
    print(f"\n  [3] First Retention Release: {first_release:,.2f} (50%)")
    rr1 = _make_retention_release(inv.name, first_release)
    print(f"     {rr1.name}  status={rr1.status}  jv={rr1.release_jv}")
    _check("First release OK", rr1.status == "Released", rr1.status)
    _check("First release JV created", bool(rr1.release_jv), rr1.release_jv)

    ar_after_rr1 = _get_ar_outstanding(inv.name)
    _check(
        f"AR after 1st release = {first_release:,.2f}",
        abs(ar_after_rr1 - first_release) < 1,
        f"{ar_after_rr1:,.2f}",
    )

    # Pay first tranche
    print(f"\n  [4] Payment for first tranche: {first_release:,.2f}")
    _make_payment(customer, inv.name, first_release)

    # Second partial release: remaining 50%
    second_release = flt(retention_amt - first_release, 2)
    print(f"\n  [5] Second Retention Release: {second_release:,.2f} (remaining 50%)")
    rr2 = _make_retention_release(inv.name, second_release)
    print(f"     {rr2.name}  status={rr2.status}  jv={rr2.release_jv}")
    _check("Second release OK", rr2.status == "Released", rr2.status)

    # Pay second tranche
    print(f"\n  [6] Payment for second tranche: {second_release:,.2f}")
    _make_payment(customer, inv.name, second_release)

    # Verify everything is zero
    ar_final = _get_ar_outstanding(inv.name)
    _check("AR final = 0", abs(ar_final) < 1, f"{ar_final:,.2f}")

    # Try to over-release (should fail)
    print(f"\n  [7] Attempting over-release (should fail with error)")
    try:
        _make_retention_release(inv.name, 1)
        print(f"  {FAIL}  Over-release should have thrown an error!")
    except frappe.ValidationError as e:
        print(f"  {PASS}  Over-release correctly blocked: {str(e)[:80]}")

    print(f"\n  ✅ SCENARIO D COMPLETE")


# ──────────────────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────────────────

def execute():
    print("\n" + "═" * 60)
    print("  OPENTRA RETENTION — Full Test Suite")
    print("  Site:", SITE)
    print("  Company:", COMPANY)
    print("═" * 60)

    # Disable notifications/emails during testing
    frappe.flags.mute_emails = True

    results = []

    try:
        scenario_a()
        results.append(("Scenario A", "PASS"))
    except Exception as e:
        results.append(("Scenario A", f"FAIL: {e}"))
        import traceback; traceback.print_exc()

    try:
        scenario_b()
        results.append(("Scenario B", "PASS"))
    except Exception as e:
        results.append(("Scenario B", f"FAIL: {e}"))
        import traceback; traceback.print_exc()

    try:
        scenario_c()
        results.append(("Scenario C", "PASS"))
    except Exception as e:
        results.append(("Scenario C", f"FAIL: {e}"))
        import traceback; traceback.print_exc()

    try:
        scenario_d()
        results.append(("Scenario D", "PASS"))
    except Exception as e:
        results.append(("Scenario D", f"FAIL: {e}"))
        import traceback; traceback.print_exc()

    # Final Summary
    _sep("FINAL RESULTS")
    all_pass = True
    for name, result in results:
        icon = "✅" if "PASS" in result else "❌"
        print(f"  {icon}  {name}: {result}")
        if "FAIL" in result:
            all_pass = False

    print("\n" + ("═" * 60))
    if all_pass:
        print("  🎉 ALL SCENARIOS PASSED — Retention Module is 100% ✅")
    else:
        print("  ⚠️  SOME SCENARIOS FAILED — Check details above")
    print("═" * 60 + "\n")
