# POC — Retention via Journal Entry

## الهدف
اختبار **افتراض واحد حرج** قبل ما نبني الـ app كامل:

> "Journal Entry مع `Cr. Debtors` + `against_voucher=SINV-xxx` يُخفّض `outstanding_amount` على الفاتورة."

## التشغيل

```bash
# 1. رفع الملف
scp poc_retention_je.py root@77.42.75.231:/tmp/

# 2. SSH + تنفيذ
ssh root@77.42.75.231
sudo chown frappe:frappe /tmp/poc_retention_je.py
sudo -iu frappe bash -c "cd /home/frappe/frappe-bench && \
    bench --site ksatest.opentra.opentech.sa console" <<'STDIN'
exec(open('/tmp/poc_retention_je.py').read())
exit()
STDIN
```

## النتائج الممكنة

### ✅ النجاح (السيناريو المتوقع 80%)
```
[Step 3] 🎯 CRITICAL CHECK — outstanding_amount AFTER Journal Entry submit
  After JE submit:
     outstanding_amount = 525,000.00
     status             = Unpaid
  ✅ SUCCESS — outstanding_amount = 525,000.00 (expected 525,000.00)
     The hook-only design is VIABLE.
```
→ **ننتقل لبناء الـ app كامل بثقة.**

### ❌ الفشل
```
  ❌ FAILURE — outstanding_amount = 575,000.00 (unchanged from 575k)
     ERPNext did NOT honor the against_voucher linkage.
     Hook-only design NOT viable. Need a different approach.
```
→ **نعيد التصميم** — ربما نحتاج override محدود لـ `calculate_outstanding_amount`.

### ⚠️ نتيجة وسط
قد يطلع `outstanding = 525k` لكن `status = "Partly Paid"` بدل `Unpaid`. هذا **مقبول** لكن يحتاج معالجة UX.

## ما أحتاج منك بعد التشغيل

**أرسل لي الـ output الكامل للـ script.** تحديداً أهتم بـ:
1. **CHECKPOINT 3** (outstanding_amount بعد JE)
2. **CHECKPOINT 4** (aggregate GL balance)
3. **Step 5** (Payment result) لو وصل له

## لو فيه خطأ في التشغيل

```python
# للتنظيف وإعادة المحاولة
import frappe
frappe.set_user("Administrator")

# احذف الـ JE أولاً، ثم الفاتورة
for je in frappe.get_all("Journal Entry",
    filters={"user_remark": ["like", "%Retention reclassification%"]}):
    doc = frappe.get_doc("Journal Entry", je.name)
    if doc.docstatus == 1:
        doc.cancel()

for inv in frappe.get_all("Sales Invoice",
    filters={"customer": "Test B2B Customer",
             "grand_total": 575000, "docstatus": 1}):
    doc = frappe.get_doc("Sales Invoice", inv.name)
    doc.cancel()

frappe.db.commit()
```

## الوقت المتوقع
- رفع + تشغيل: 5 دقائق
- قراءة النتائج: 5 دقائق
- **إجمالي: 10 دقائق من وقتك**

مقابل حماية ~4 ساعات من عمل محتمل مُهدَر.
