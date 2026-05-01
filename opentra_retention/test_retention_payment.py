"""
اختبار Payment Entry للـ Retention
- ينشئ Payment Entry بـ custom_is_retention_payment = 1 بمبلغ 50,000
- يتحقق أن GL: DR Cash, CR Retention Receivable (لا AR)
- يتحقق من get_retention_summary API بعد الدفع
"""

import frappe
from frappe.utils import nowdate

COMPANY   = "KSA Test Company"
CUSTOMER  = "Test B2C Customer"
INVOICE   = "ACC-SINV-2026-00008"
RET_ACCT  = "Retention Receivable - KTC"
AR_ACCT   = "Debtors - KTC"
CASH_ACCT = "Cash - KTC"
RET_AMT   = 50000.0


def _get_or_create_mode_of_payment(company, cash_account):
    """اجلب أو أنشئ Mode of Payment يناسب الاختبار."""
    rows = frappe.db.sql(
        "SELECT name FROM `tabMode of Payment` ORDER BY name LIMIT 5",
        as_dict=1,
    )
    if rows:
        print(f"   Modes of Payment المتاحة: {[r.name for r in rows]}")
        return rows[0].name

    # لا يوجد → أنشئ "Cash" جديد
    print("   ℹ️  لا يوجد Mode of Payment → سننشئ 'Cash'...")
    mop = frappe.new_doc("Mode of Payment")
    mop.mode_of_payment = "Cash"
    mop.type = "Cash"
    # ksa_compliance يضيف هذا الحقل الإجباري (ZATCA Payment Means: 10 = Cash)
    mop.custom_zatca_payment_means_code = "10"
    mop.append("accounts", {
        "company": company,
        "default_account": cash_account,
    })
    mop.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"   ✅ تم إنشاء Mode of Payment: {mop.name}")
    return mop.name


def run():
    print("\n" + "="*60)
    print("🧪 اختبار Retention Payment Entry")
    print("="*60)

    # ── 1. حالة الفاتورة قبل الدفع ─────────────────────────────
    inv = frappe.get_doc("Sales Invoice", INVOICE)
    print(f"\n📄 الفاتورة: {INVOICE}")
    print(f"   Grand Total:       {inv.grand_total:>12,.2f} SAR")
    print(f"   Retention Amount:  {inv.custom_retention_amount:>12,.2f} SAR")
    print(f"   Outstanding (AR):  {inv.outstanding_amount:>12,.2f} SAR")
    print(f"   Retention JV:      {inv.custom_retention_jv}")

    # ── 2. رصيد Retention Receivable قبل الدفع ─────────────────
    ret_bal_before = frappe.db.sql("""
        SELECT COALESCE(SUM(debit - credit), 0) AS bal
        FROM `tabGL Entry`
        WHERE account = %s AND company = %s AND is_cancelled = 0
    """, (RET_ACCT, COMPANY), as_dict=1)[0].bal

    print(f"\n💰 رصيد {RET_ACCT} قبل الدفع: {ret_bal_before:,.2f} SAR")

    # ── 3. إنشاء Retention Payment Entry ───────────────────────
    print(f"\n⚙️  إنشاء Payment Entry للاستقطاع ({RET_AMT:,.0f} SAR)...")

    # اجلب أو أنشئ Mode of Payment
    mop = _get_or_create_mode_of_payment(COMPANY, CASH_ACCT)
    if not mop:
        print("   ❌ فشل إنشاء Mode of Payment!")
        return

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type                = "Receive"
    pe.company                     = COMPANY
    pe.posting_date                = nowdate()
    pe.mode_of_payment             = mop
    pe.party_type                  = "Customer"
    pe.party                       = CUSTOMER
    pe.paid_from                   = AR_ACCT  # سيُستبدل بـ on_validate
    pe.paid_to                     = CASH_ACCT
    pe.paid_amount                 = RET_AMT
    pe.received_amount             = RET_AMT
    pe.target_exchange_rate        = 1.0
    pe.source_exchange_rate        = 1.0
    pe.custom_is_retention_payment = 1
    # ⚠️ بدون references: الـ Retention Payment لا يُغلق AR الفاتورة
    # (AR يُغلق بدفع عادي للـ 525K، أما الـ Retention يُغلق Retention Receivable مباشرة)

    pe.insert(ignore_permissions=True)
    print(f"   ✅ تم الإنشاء: {pe.name}")
    print(f"   paid_from بعد validate: {pe.paid_from}")

    # ── 4. Submit ────────────────────────────────────────────────
    print(f"\n⚙️  Submitting...")
    pe.submit()
    print(f"   ✅ Submitted: {pe.name}")

    # ── 5. GL Entries ────────────────────────────────────────────
    gl_entries = frappe.db.sql("""
        SELECT account, debit, credit, party_type, party
        FROM `tabGL Entry`
        WHERE voucher_no = %s AND is_cancelled = 0
        ORDER BY debit DESC
    """, pe.name, as_dict=1)

    print(f"\n📊 GL Entries لـ {pe.name}:")
    print(f"   {'Account':<35} {'Debit':>12} {'Credit':>12}  Party")
    print(f"   {'-'*35} {'-'*12} {'-'*12}  {'-'*20}")
    for gl in gl_entries:
        party = f"{gl.party_type}: {gl.party}" if gl.party else ""
        print(f"   {gl.account:<35} {gl.debit:>12,.2f} {gl.credit:>12,.2f}  {party}")

    # ── 6. التحقق من صحة الـ GL ─────────────────────────────────
    print(f"\n🔍 التحقق:")
    dr_cash      = next((g for g in gl_entries if g.account == CASH_ACCT and g.debit > 0), None)
    cr_retention = next((g for g in gl_entries if g.account == RET_ACCT  and g.credit > 0), None)
    cr_ar        = next((g for g in gl_entries if g.account == AR_ACCT   and g.credit > 0), None)

    if dr_cash:
        print(f"   ✅ DR {CASH_ACCT}: {dr_cash.debit:,.2f}")
    else:
        print(f"   ❌ لا يوجد DR على Cash!")

    if cr_retention:
        print(f"   ✅ CR {RET_ACCT}: {cr_retention.credit:,.2f}")
    else:
        print(f"   ❌ لا يوجد CR على Retention Receivable!")

    if cr_ar:
        print(f"   ⚠️  CR {AR_ACCT}: {cr_ar.credit:,.2f} (المفروض صفر)")
    else:
        print(f"   ✅ لا يوجد CR على AR (صحيح!)")

    # ── 7. رصيد Retention Receivable بعد الدفع ─────────────────
    ret_bal_after = frappe.db.sql("""
        SELECT COALESCE(SUM(debit - credit), 0) AS bal
        FROM `tabGL Entry`
        WHERE account = %s AND company = %s AND is_cancelled = 0
    """, (RET_ACCT, COMPANY), as_dict=1)[0].bal

    print(f"\n💰 رصيد {RET_ACCT}:")
    print(f"   قبل الدفع: {ret_bal_before:>10,.2f} SAR")
    print(f"   بعد الدفع: {ret_bal_after:>10,.2f} SAR")
    if ret_bal_after == 0:
        print(f"   ✅ الرصيد = صفر (الاستقطاع مُسدَّد بالكامل)")
    else:
        print(f"   ℹ️  الرصيد المتبقي: {ret_bal_after:,.2f}")

    # ── 8. API: get_retention_summary ────────────────────────────
    print(f"\n📡 get_retention_summary:")
    try:
        from opentra_retention.api import get_retention_summary
        s = get_retention_summary(company=COMPANY)
        print(f"   Invoices with Retention: {s.get('total_invoices_with_retention')}")
        print(f"   Total Retention Amt:     {s.get('total_retention_amount'):>10,.2f} SAR")
        print(f"   Total Released:          {s.get('total_retention_released'):>10,.2f} SAR")
        print(f"   Total Outstanding:       {s.get('total_retention_outstanding'):>10,.2f} SAR")
        print(f"   Retention Account:       {s.get('retention_account')}")
        outstanding = s.get('total_retention_outstanding') or 0
        if outstanding == 0:
            print(f"   ✅ Outstanding = صفر")
        else:
            print(f"   ℹ️  لا يزال هناك استقطاع معلق: {outstanding:,.2f} SAR")
    except Exception as e:
        print(f"   ⚠️  خطأ: {e}")

    # ── 9. النتيجة النهائية ──────────────────────────────────────
    passed = bool(dr_cash and cr_retention and not cr_ar)
    print("\n" + "="*60)
    if passed:
        print("🎯 ✅ الاختبار نجح 100%")
    else:
        print("🎯 ❌ الاختبار فشل — راجع الأخطاء أعلاه")
    print("="*60 + "\n")
