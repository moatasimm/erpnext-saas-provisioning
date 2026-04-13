# Opentra SaaS — Decisions Log

> **Purpose:** ملخص مختصر لكل القرارات المعمارية المحسومة. يُقرأ في بداية كل جلسة جديدة لاستعادة السياق بسرعة.
>
> **آخر تحديث:** 13 أبريل 2026 (v0.4)

---

## ✅ القرارات المحسومة

### المنتج
1. **الاسم:** Opentra
2. **النطاق الأساسي:** `opentra.opentech.sa`
3. **الأسواق:** السعودية (أولاً) + خليج + الأردن
4. **اللغات:** عربي + إنجليزي

### البوابات والنطاقات
5. **Public Site:** `opentra.opentech.sa` — Next.js 15 + Tailwind + shadcn/ui + Framer Motion
6. **Customer Portal:** `portal.opentra.opentech.sa` — نفس Stack
7. **Admin Panel:** `admin.opentra.opentech.sa` — Frappe app `opentra_admin` على Admin Server
8. **Demo:** `demo.opentra.opentech.sa` — عام، مقاولات، reset يومي
9. **مواقع العملاء:** `<customer>.opentra.opentech.sa`

### البنية التحتية
10. **Customer Server:** Hetzner 77.42.75.231 — Frappe bench متعدد المواقع
11. **Admin Server:** 45.90.220.57 (`erp.opentech.sa`) — ERPNext داخلي (موجود)
12. **Provisioning API:** Flask على Customer Server port 5000

### الأمان والمصادقة
13. **Internal API:** JWT signed + mTLS
14. **Customer Auth:** OAuth2 (Admin Server = provider)

---

## 🆕 القرارات الجديدة في v0.4 (13 أبريل 2026)

### 🇸🇦 ZATCA Compliance Strategy — HYBRID

بعد smoke test كامل end-to-end على `ksatest.opentra.opentech.sa`:

#### ✅ قرار: اعتماد `ksa_compliance` (LavaLoon) لـ ZATCA
- **الإصدار المعتمد:** `v0.60.1` master
- **السبب:** 6/6 ZATCA compliance checks Accepted من sandbox
- **المطوّر:** LavaLoon (موثوق، نشط، community-backed)
- **Repo:** https://github.com/lavaloon-eg/ksa_compliance

#### ❌ رفض: `zatca_integration` (الحالي)
- **السبب:** يحتاج 4 patches يدوية + retention معيوب محاسبياً
- **القرار:** **يُستبدل كلياً** بـ `ksa_compliance` في كل المواقع الجديدة
- **المواقع القديمة:** خطة migration في Sprint منفصل

### 🏗️ Retention Strategy — CUSTOM BUILD

اختبار Construction Retention أثبت أن:

#### ❌ ERPNext native **لا يدعم** Construction Retention محاسبياً
- Payment Terms Template يؤجّل الـ payment schedule فقط (soft split)
- GL entries تسجّل المبلغ الكامل في `Debtors` بدون فصل
- لا يوجد حساب `Retention Receivable` منفصل في الـ journal

#### ❌ KSA Compliance لا يوفّر retention
- DocTypes فيه كلها ZATCA-only
- صفر custom fields للـ retention على Sales Invoice

#### ✅ قرار: بناء `opentra_retention` من الصفر
- **Scope:** Custom Frappe app مستقل
- **Approach:** Override `make_gl_entries` + Custom Fields على Sales Invoice
- **Timeline:** Sprint 5 (لم يتغيّر من v0.3)
- **التفاصيل الكاملة:** راجع `SESSION_LOG_2026-04-13.md` section "opentra_retention Schema"

---

## 💰 Pricing Model: Hybrid

### مسارين للعميل
- **Quick Start (Tiered Plans):** Starter/Growth/Business/Enterprise
- **Build Your Own (Modular):** اختيار موديول موديول

### Mandatory Base
1. Core Platform
2. Accounting
3. ZATCA (للسعودية فقط) — **الآن = `ksa_compliance` من LavaLoon**

### نماذج التسعير
- `flat`, `per_user`, `per_transaction`, `tiered`

### العملات (Manual pricing)
SAR, AED, KWD, QAR, BHD, OMR, JOD, USD

### دورة حياة العميل (Customer Lifecycle)
- Demo عام (no signup)
- Trial 14 يوم (قابل للتعديل)
- Extended Trial +30 يوم عند الطلب
- **لا Free Forever tier**
- Enterprise: Custom Quote عبر `Opentra Lead`

---

## 🔄 Site Lifecycle (4 مراحل)

**قاعدة أساسية:** لا حذف تلقائي للبيانات أبداً. الحذف فقط بقرار إداري أو طلب صريح من العميل.

```
Active → Expired (Grace) → Suspended → Archived → [Manual Delete Only]
```

| المرحلة | المدة الافتراضية | ماذا يحدث | الإحياء |
|---|---|---|---|
| **Active** | حسب الاشتراك | كل شيء يعمل عادي | — |
| **Expired** | 30 يوم | Read-only، لا إضافة، إشعارات يومية، زر دفع بارز | دفع فوري → Active |
| **Suspended** | 60 يوم | الموقع مُقفل كلياً، DB محفوظة | دفع + طلب إعادة تفعيل (1-3 أيام) |
| **Archived** | ∞ | DB مضغوطة في cold storage، site مزال من bench | دفع + Restore Fee + طلب (3-7 أيام) |
| **Deleted** | — | لا يحدث تلقائياً | — |

### لماذا هذا النموذج؟
- مصداقية تجارية (بيانات آمنة دائماً)
- 40% من العملاء المتركين يعودون خلال 6 أشهر
- ZATCA يتطلب 10 سنوات احتفاظ
- تكلفة cold storage منخفضة (~0.1 SAR/GB/شهر)

### Restore Fees
- القيمة ديناميكية من الإعدادات
- القيمة الافتراضية: **300 SAR** (قابلة للتعديل)

---

## ⚙️ `Opentra Lifecycle Settings` (Single DocType)

كل قيم الـ Lifecycle تُدار من شاشة واحدة — لا قيم مُترمَّزة في الكود.

**الحقول:**
- `trial_days` (default: 14)
- `extended_trial_days` (default: 30)
- `grace_period_days` (default: 30)
- `suspended_period_days` (default: 60)
- `restore_fee` (default: 300)
- `restore_fee_currency` (default: SAR)
- `notify_before_expiry_days` (default: 7)
- `notify_before_suspend_days` (default: 5)
- `send_daily_reminders_in_expired` (default: true)
- `enable_self_service_restore` (default: false)
- `cold_storage_path`
- `auto_backup_before_archive` (default: true)

---

## 🗺️ Feature Dependency Graph

### قاعدة حرجة
لا يمكن تفعيل ميزة دون تفعيل تبعياتها.

### الهرم (محدّث v0.4)
```
                 Core Platform (Required)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Accounting       HR        Inventory
    (Mandatory)       │            │
          │           │            │
    ┌─────┼─────┬─────┼───┐        │
    ▼     ▼     ▼     ▼   ▼        ▼
 ZATCA*  CRM  Projects  Payroll  POS
 (KSA:R)                   │
    │                      ▼
    │                  Retention**
    │          (Accounting + Projects)
    │
    * ZATCA = ksa_compliance (LavaLoon)
    ** Retention = opentra_retention (custom build)
```

### جدول الاعتماديات

| Feature | Requires | Source |
|---|---|---|
| Core Platform | — (base) | `opentra_core` |
| **Accounting** | Core (mandatory) | ERPNext |
| **ZATCA** | Core + Accounting (mandatory KSA) | `ksa_compliance` (LavaLoon) |
| CRM | Core + Accounting | ERPNext |
| Inventory | Core + Accounting | ERPNext |
| POS | Core + Accounting + Inventory | ERPNext |
| HR | Core | ERPNext HR |
| Payroll KSA | Core + HR + Accounting | ERPNext Payroll |
| Payroll GCC | Core + HR + Accounting | ERPNext Payroll |
| Projects | Core + Accounting | ERPNext |
| Manufacturing | Core + Accounting + Inventory | ERPNext |
| **Retention** | Core + Accounting + Projects | **`opentra_retention`** (custom) |
| Assets | Core + Accounting | ERPNext |
| Warehouse | Core + Accounting + Inventory | ERPNext |
| Custom Reports | Core | `opentra_core` |
| ZATCA Premium | ZATCA + Accounting | TBD |

---

## 📦 Pricing Engine DocTypes (Admin Server)

1. `Opentra Pricing Plan`
2. `Opentra Feature`
3. `Opentra Feature Dependency` (child table)
4. `Opentra User Pricing Tier`
5. `Opentra Storage Pricing`
6. `Opentra Discount Rule`
7. `Opentra Pricing Settings`
8. `Opentra Currency Pricing`
9. `Opentra Lead` (Enterprise)
10. `Opentra Service Catalog`
11. `Opentra Lifecycle Settings` (Single — إعدادات Site Lifecycle)
12. `Opentra Site` (سجل كل موقع عميل + lifecycle_status)

---

## 🧩 Feature Catalog (محدّث v0.4)

| Feature | Technical Name | Pricing Model | Source |
|---|---|---|---|
| Core Platform | `opentra_core` | Base (mandatory) | Opentra |
| Accounting | `erpnext_accounting` | Base (mandatory) | ERPNext |
| **ZATCA** | **`ksa_compliance`** | Base (mandatory for KSA) | **LavaLoon** |
| CRM | `erpnext_crm` | flat | ERPNext |
| Inventory | `erpnext_inventory` | flat | ERPNext |
| POS | `erpnext_pos` | flat | ERPNext |
| HR | `erpnext_hr` | flat | ERPNext |
| HR Premium | `opentra_hr_premium` | per_user | Opentra |
| Payroll KSA | `erpnext_payroll_ksa` | per_user | ERPNext |
| Payroll GCC | `erpnext_payroll_gcc` | per_user | ERPNext |
| Projects | `erpnext_projects` | flat | ERPNext |
| Manufacturing | `erpnext_manufacturing` | flat | ERPNext |
| Warehouse | `erpnext_warehouse` | flat | ERPNext |
| **Retention** | **`opentra_retention`** | flat | **Opentra (new)** |
| Assets | `erpnext_assets` | flat | ERPNext |
| ZATCA Premium | `opentra_zatca_premium` | per_transaction | Opentra |
| Custom Reports | `opentra_reports` | flat | Opentra |

---

## 🎯 الأولويات للجلسة القادمة

### Sprint 5: `opentra_retention` — HIGHEST PRIORITY

**راجع `SESSION_LOG_2026-04-13.md` للتفاصيل الكاملة:**
- DocTypes Schema (Custom Fields + new DocTypes)
- GL Override Strategy
- Test cases
- Integration with ZATCA

---

## 🔴 مشاكل معروفة

### ~~Retention الحالي معيوب محاسبياً~~ → **مُحسم في v0.4**
- **القرار:** `opentra_retention` app جديد (بناءً على اختبار مُثبت)
- **Status:** Schema جاهز، POC في Sprint 5

### Flask API jobs لا تُشارَك بين workers
- **الحل المؤجل:** Redis

### `opentra_admin` غير موجود بعد
- **Status:** Sprint 2

### KSA Compliance Gotchas (للـ provisioning automation)
1. Tax Category يحتاج `custom_zatca_category` = "Standard rate" (أو ما يناسب)
2. Sales Tax Template يحتاج `tax_category` link
3. Customer يحتاج `tax_id` (B2B) + address (for Standard invoices)
4. Item Tax Template يحتاج VAT account

هذه Gotchas **غير موثّقة رسمياً** في LavaLoon docs. لازم تُعالَج تلقائياً في `opentra_core` provisioning script.

---

## 📝 ملاحظات للجلسة القادمة

1. اقرأ `ARCHITECTURE.md` + `DECISIONS.md` + `SESSION_LOG_2026-04-13.md` من GitHub
2. **أول عمل:** بناء `opentra_retention` app على Customer Server (نسخة POC على ksatest)
3. **ثاني عمل:** Custom Fields على Sales Invoice + GL override
4. **ثالث عمل:** اختبار Sales Invoice بـ Retention → تأكد ZATCA لا يزال Accepted
5. **رابع عمل:** Retention Release mechanism (Journal Entry عند اكتمال المشروع)
6. **خامس عمل:** توثيق + push على GitHub

---

## 🗂️ GitHub References

- Repo: https://github.com/moatasimm/erpnext-saas-provisioning
- ARCHITECTURE.md: `/ARCHITECTURE.md`
- DECISIONS.md: `/DECISIONS.md` (هذا الملف)
- SESSION_LOG_2026-04-13.md: `/sessions/SESSION_LOG_2026-04-13.md` (جديد)

---

## 📚 مراجع

- [Frappe Docs](https://frappeframework.com/docs)
- [ERPNext Docs](https://docs.erpnext.com)
- [ZATCA Portal](https://zatca.gov.sa)
- [KSA Compliance (LavaLoon)](https://github.com/lavaloon-eg/ksa_compliance)
- [Next.js 15](https://nextjs.org/docs)
- [shadcn/ui](https://ui.shadcn.com)

---

## 🏷️ Version History

- **v0.1** — Initial setup (March 2026)
- **v0.2** — Pricing Engine + Feature Dependencies
- **v0.3** — Lifecycle Settings + Site Lifecycle (11 April 2026)
- **v0.4** — ZATCA strategy finalized (ksa_compliance) + Retention custom build confirmed (13 April 2026)
