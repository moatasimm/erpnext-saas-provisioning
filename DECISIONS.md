# Opentra SaaS — Decisions Log

> **Purpose:** ملخص مختصر لكل القرارات المعمارية المحسومة. يُقرأ في بداية كل جلسة جديدة لاستعادة السياق بسرعة.
>
> **آخر تحديث:** 11 أبريل 2026 (v0.3)

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
11. **Admin Server:** ERPNext داخلي (موجود)
12. **Provisioning API:** Flask على Customer Server port 5000

### الأمان والمصادقة
13. **Internal API:** JWT signed + mTLS
14. **Customer Auth:** OAuth2 (Admin Server = provider)

---

## 💰 Pricing Model: Hybrid

### مسارين للعميل
- **Quick Start (Tiered Plans):** Starter/Growth/Business/Enterprise
- **Build Your Own (Modular):** اختيار موديول موديول

### Mandatory Base
1. Core Platform
2. Accounting
3. ZATCA (للسعودية فقط)

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
| **Suspended** | 60 يوم | **الموقع مُقفل كلياً**، DB محفوظة | دفع + طلب إعادة تفعيل (1-3 أيام) |
| **Archived** | ∞ | DB مضغوطة في cold storage، site مزال من bench | دفع + Restore Fee + طلب (3-7 أيام) |
| **Deleted** | — | **لا يحدث تلقائياً** | — |

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

كل قيم الـ Lifecycle تُدار من شاشة واحدة — **لا قيم مُترمَّزة في الكود**.

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
- `cold_storage_path` — مسار الأرشفة
- `auto_backup_before_archive` (default: true)

---

## 🗺️ Feature Dependency Graph

### قاعدة حرجة
لا يمكن تفعيل ميزة دون تفعيل تبعياتها.

### الهرم
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
  ZATCA  CRM  Projects  Payroll  POS
 (KSA:R)                   │
                           ▼
                       Retention
               (Accounting + Projects)
```

### جدول الاعتماديات

| Feature | Requires |
|---|---|
| Core Platform | — (base) |
| **Accounting** | Core (mandatory) |
| **ZATCA** | Core + Accounting (mandatory for KSA) |
| CRM | Core + Accounting |
| Inventory | Core + Accounting |
| POS | Core + Accounting + Inventory |
| HR | Core |
| Payroll KSA | Core + HR + Accounting |
| Payroll GCC | Core + HR + Accounting |
| Projects | Core + Accounting |
| Manufacturing | Core + Accounting + Inventory |
| **Retention** | Core + Accounting + Projects |
| Assets | Core + Accounting |
| Warehouse | Core + Accounting + Inventory |
| Custom Reports | Core |
| ZATCA Premium | ZATCA + Accounting |

### Activation Rules
عند اختيار ميزة بدون تبعياتها:
- Popup: "تتطلب X, Y. إضافة؟ (+السعر)"
- موافق → إضافة التبعيات تلقائياً
- رجوع → إلغاء الاختيار

### Deactivation Rules
عند إلغاء ميزة تعتمد عليها أخرى:
- تحذير: "مطلوبة من A, B. إلغاء كل هذه؟"
- النظام يُلغي الـ dependent chain تلقائياً عند الموافقة

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

## 🧩 Feature Catalog

| Feature | Technical Name | Pricing Model |
|---|---|---|
| Core Platform | `opentra_core` | Base (mandatory) |
| Accounting | `opentra_accounting` | Base (mandatory) |
| ZATCA | `opentra_zatca` | Base (mandatory for KSA) |
| CRM | `opentra_crm` | flat |
| Inventory | `opentra_inventory` | flat |
| POS | `opentra_pos` | flat |
| HR | `opentra_hr` | flat |
| HR Premium | `opentra_hr_premium` | per_user |
| Payroll KSA | `opentra_payroll_ksa` | per_user |
| Payroll GCC | `opentra_payroll_gcc` | per_user |
| Projects | `opentra_projects` | flat |
| Manufacturing | `opentra_manufacturing` | flat |
| Warehouse | `opentra_warehouse` | flat |
| Retention | `opentra_retention` | flat |
| Assets | `opentra_assets` | flat |
| ZATCA Premium | `opentra_zatca_premium` | per_transaction |
| Custom Reports | `opentra_reports` | flat |

---

## 🎯 الأولويات للجلسة القادمة

### Section 4: Component Details
- `opentra_admin`, `opentra_core`, Public Site, Customer Portal

### Section 5: DocTypes Schemas الكاملة
- 12 DocType (بما فيها `Opentra Lifecycle Settings`)
- Feature Dependencies logic
- Site Lifecycle state machine

### Section 6: API Contracts
- Public pricing API
- Internal API (Admin ↔ Customer Server)
- Lifecycle management API (suspend, archive, restore)

### Section 7: Security Model
mTLS + JWT + OAuth2 + Secrets

### Section 8: Deployment Plan
CI/CD + deploy strategy

### Section 9: Milestones
- Sprint 1: `opentra_core` foundations
- Sprint 2: `opentra_admin` + Pricing Engine + Lifecycle DocTypes
- Sprint 3: Public Site
- Sprint 4: Customer Portal
- Sprint 5: `opentra_retention` rebuild
- Sprint 6: Lifecycle automation (scheduled jobs)
- Sprint 7: Polish + Soft Launch

---

## 🔴 مشاكل معروفة

### Retention الحالي معيوب محاسبياً
- GL entries خاطئة
- `outstanding_amount` يشمل retention
- **القرار:** إعادة بناء في `opentra_retention`

### Flask API jobs لا تُشارَك بين workers
- **الحل المؤجل:** Redis

### `opentra_admin` غير موجود بعد
- أول عمل في الجلسة القادمة

---

## 📝 ملاحظات للجلسة القادمة

1. اقرأ `ARCHITECTURE.md` + `DECISIONS.md` من GitHub
2. **أول عمل:** إنشاء Frappe app `opentra_admin` على Admin Server
3. **ثاني عمل:** DocTypes الـ Pricing Engine (ابدأ بـ `Opentra Feature`)
4. **ثالث عمل:** Feature Dependencies logic + validation
5. **رابع عمل:** `Opentra Lifecycle Settings` + state machine
6. **خامس عمل:** Public API `/api/public/pricing`

---

## 🗂️ GitHub References

- Repo: https://github.com/moatasimm/erpnext-saas-provisioning
- ARCHITECTURE.md: `/ARCHITECTURE.md`
- DECISIONS.md: `/DECISIONS.md` (هذا الملف)

---

## 📚 مراجع

- [Frappe Docs](https://frappeframework.com/docs)
- [ERPNext Docs](https://docs.erpnext.com)
- [ZATCA Portal](https://zatca.gov.sa)
- [Next.js 15](https://nextjs.org/docs)
- [shadcn/ui](https://ui.shadcn.com)
