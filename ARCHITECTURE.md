# Opentra SaaS — Architecture Document

> **آخر تحديث:** 11 أبريل 2026
> **الإصدار:** 0.1 (Initial Draft)
> **المؤلفون:** Moatasim Almalki + Claude

---

## 1. نظرة عامة / Overview

### 1.1 الرؤية / Vision

**Opentra** هو منتج SaaS لتقديم ERPNext كخدمة مُدارة للشركات الصغيرة والمتوسطة في **المملكة العربية السعودية ودول الخليج والأردن**، مع تكامل كامل مع ZATCA (Phase 1 & 2) وميزات صناعية مخصصة.

النموذج التجاري قائم على **modular subscriptions**: العميل يشترك في الميزات التي يحتاجها فقط (محاسبة، HR، رواتب، Retention، إلخ) ويدفع بناءً على اختياره، مع إمكانية إضافة أو إزالة الميزات في أي وقت.

### 1.2 الأسواق المستهدفة / Target Markets

| السوق | الحالة |
|---|---|
| 🇸🇦 المملكة العربية السعودية | Primary — ZATCA ready |
| 🇰🇼 الكويت | Secondary |
| 🇦🇪 الإمارات | Secondary |
| 🇶🇦 قطر | Secondary |
| 🇧🇭 البحرين | Secondary |
| 🇴🇲 عُمان | Secondary |
| 🇯🇴 الأردن | Secondary |

### 1.3 المنافسون / Competitors

- **Odoo Online** (عالمي، لا يدعم ZATCA natively)
- **Zoho Books** (محاسبة فقط، محدود)
- **Qoyod** (سعودي، محاسبة فقط)
- **Wafeq** (سعودي، محاسبة فقط)
- **Daftra** (مصري، محاسبة وفواتير)

**ميزة Opentra التنافسية:** منصة ERP كاملة (ليست محاسبة فقط) مع ZATCA + تخصيصات صناعية (مقاولات، تجزئة، تصنيع) + بنية modular تسمح للعميل بالدفع حسب الحاجة.

---

## 2. النموذج التجاري / Business Model

### 2.1 Dynamic Pricing Engine

التسعير في Opentra **ديناميكي بالكامل** — يُدار من Admin Panel عبر DocTypes قابلة للتعديل في الواجهة دون الحاجة لتعديل الكود أو إعادة النشر.

#### 2.1.1 المكونات الرئيسية

**الـ DocTypes المكوّنة للـ Pricing Engine (على Admin Server):**

1. **`Opentra Pricing Plan`** — الخطط الأساسية (Starter, Growth, Business, Enterprise)
2. **`Opentra Feature`** — الميزات الإضافية (Retention, HR, Payroll, etc.)
3. **`Opentra User Pricing Tier`** — شرائح تسعير المستخدمين الإضافيين
4. **`Opentra Storage Pricing`** — شرائح تسعير التخزين الإضافي
5. **`Opentra Discount Rule`** — قواعد الخصم (سنوي، promo codes، volume)
6. **`Opentra Pricing Settings`** — إعدادات عامة (VAT, currencies, trial days)
7. **`Opentra Currency Pricing`** — تسعير يدوي لكل عملة (SAR, AED, KWD, USD)
8. **`Opentra Lead`** — طلبات Enterprise Custom Quote

> **تفاصيل الـ Schema الكاملة لكل DocType في Section 5.**

#### 2.1.2 نماذج التسعير / Pricing Models

كل ميزة تستخدم واحداً من 4 نماذج:

| النموذج | الوصف | مثال |
|---|---|---|
| `flat` | سعر ثابت شهري | Retention = 50 SAR/شهر |
| `per_user` | سعر لكل مستخدم | HR Premium = 10 SAR/user/شهر |
| `per_transaction` | سعر لكل معاملة | ZATCA Premium = 0.5 SAR/فاتورة |
| `tiered` | شرائح تنازلية | User tiers: 1-10 بـ X، 11-50 بـ Y |

#### 2.1.3 دعم العملات المتعددة

**العملات المدعومة (Phase 1):**
- 🇸🇦 SAR — Saudi Riyal (Primary)
- 🇦🇪 AED — UAE Dirham
- 🇰🇼 KWD — Kuwaiti Dinar
- 🇶🇦 QAR — Qatari Riyal
- 🇧🇭 BHD — Bahraini Dinar
- 🇴🇲 OMR — Omani Rial
- 🇯🇴 JOD — Jordanian Dinar
- 🇺🇸 USD — US Dollar (للعملاء الدوليين)

**المنهجية:** تسعير **يدوي** لكل عملة (ليس تحويل تلقائي من SAR).

**السبب:**
- يحميك من تقلبات أسعار الصرف
- يسمح بتسعير نفسي (99 SAR لا تصبح 97.43 AED عشوائياً)
- مرونة أعلى للتخصيص حسب السوق المحلي
- معيار SaaS الاحترافي (Stripe, Linear, Notion كلها تفعل هذا)

**التطبيق:** `Opentra Currency Pricing` DocType يحتوي سجلاً لكل (Plan/Feature × Currency) مع السعر اليدوي.

#### 2.1.4 الخطط الأساسية — Structure (القيم المبدئية في الإعدادات)

| Plan | Users | Storage | Description |
|---|---|---|---|
| Starter | 3 | 5 GB | للشركات الناشئة |
| Growth | 10 | 20 GB | للشركات النامية |
| Business | 25 | 50 GB | للشركات المتوسطة |
| Enterprise | Custom | Custom | **Custom Quote** عبر فورم |

**الأسعار لا تُكتب هنا** — هي قيم في قاعدة البيانات تُعدَّل من Admin Panel.

#### 2.1.5 الميزات الإضافية — Catalog الأولي

| Feature | Technical Name | Default Model |
|---|---|---|
| Retention Management | `opentra_retention` | flat |
| Advanced HR | `opentra_hr_premium` | per_user |
| Payroll KSA (GOSI) | `opentra_payroll_ksa` | per_user |
| Payroll GCC | `opentra_payroll_gcc` | per_user |
| ZATCA Phase 2 Premium | `opentra_zatca_premium` | per_transaction |
| Custom Reports Pack | `opentra_reports` | flat |
| Point of Sale | `opentra_pos` | flat |
| Manufacturing | `opentra_manufacturing` | flat |
| Warehouse Management | `opentra_warehouse` | flat |
| Project Management | `opentra_projects` | flat |

**هذه القائمة تنمو بمرور الوقت** — كل ميزة جديدة تُضاف عبر إنشاء Frappe app + تسجيلها في `Opentra Feature` DocType.

#### 2.1.6 قواعد الخصم / Discount Rules

يمكن إنشاء قواعد خصم ديناميكية من Admin Panel:

| نوع القاعدة | الوصف | مثال |
|---|---|---|
| `billing_cycle` | خصم للدفع السنوي | 15% عند اختيار سنوي |
| `promo_code` | كود ترويجي | LAUNCH20 = 20% |
| `min_features` | خصم عند شراء ميزات كثيرة | 3+ ميزات = 10% |
| `customer_group` | خصم لفئة عملاء | شركات ناشئة = 25% |
| `volume_users` | خصم حسب عدد المستخدمين | 50+ users = 10% |

#### 2.1.7 Enterprise Custom Quote Flow

للعملاء الكبار الذين يحتاجون تسعير مخصص:

1. العميل في صفحة Pricing يضغط **"Contact Sales"** على خطة Enterprise
2. يملأ فورم: اسم الشركة، الحجم، المتطلبات، ميزانية تقديرية
3. الفورم ينشئ `Opentra Lead` في Admin Server
4. إشعار يصل لموظف المبيعات + بريد إلكتروني
5. الموظف يتواصل ويُعدّ **Opentra Quotation** مخصصة
6. بعد الموافقة، تتحوّل لـ `Opentra Subscription` عادية

### 2.2 دورة حياة العميل / Customer Lifecycle

```
Landing ──► Demo Explore (anonymous)
    │           │
    │           ▼
    └──► Signup ──► Trial (14 days) ──┬──► Active Subscription
                        │              │
                        │              └──► Expired ──► Grace (30 days) ──► Deletion
                        │
                        └──► Extended Trial (30 days, on request)
```

**المراحل تفصيلياً:**

| المرحلة | المدة | الوصف |
|---|---|---|
| **Demo** | دائم | `demo.opentra.opentech.sa` — استكشاف بدون تسجيل، reset يومي |
| **Signup** | لحظي | العميل يختار خطة + ميزات، يُنشأ حساب + موقع Trial |
| **Trial** | 14 يوم | استخدام كامل بدون دفع، موقع حقيقي مُجهّز مسبقاً |
| **Extended Trial** | +30 يوم | عند الطلب للعملاء الجادين |
| **Active** | حسب الاشتراك | مدفوع، شهري أو سنوي |
| **Grace Period** | 30 يوم | عند عدم التجديد: read-only + إشعارات |
| **Deletion** | بعد grace | حذف البيانات نهائياً، إشعار أخير قبل 7 أيام |

**قرار واعي:** لا يوجد Free Forever tier.

**السبب:** ERPNext يحتاج موارد دائمة لكل موقع، والعملاء المجانيون لا يتحولون عادةً إلى مدفوعين في B2B SaaS. Demo العام + Trial القوي يُحقّقان نفس الغرض التسويقي بتكلفة أقل.

### 2.3 خدمات إضافية / Additional Services

خارج الاشتراك الأساسي، تتوفر خدمات one-time أو متكررة:

| الخدمة | النوع | الوصف |
|---|---|---|
| Enhanced Backups | Monthly | نسخ احتياطية يومية + احتفاظ طويل |
| Premium Support (SLA) | Monthly | ضمان استجابة خلال X ساعة |
| Training Sessions | One-time | تدريب أونلاين للموظفين |
| Custom Development | One-time | تخصيص تقارير، واجهات، workflows |
| Data Migration | One-time | ترحيل بيانات من نظام قديم |
| Dedicated Server | Monthly | موقع مستقل على سيرفر خاص (Enterprise) |

**كل هذه الخدمات تُدار عبر `Opentra Service Catalog` DocType** في Admin Panel، قابل للتعديل والتسعير الديناميكي.

---

## 3. المعمارية عالية المستوى / High-Level Architecture

### 3.1 المخطط العام

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                     │
└──────────┬─────────────────────┬────────────────────┬───────────────────┘
           │                     │                    │
           ▼                     ▼                    ▼
    ┌─────────────┐      ┌──────────────┐     ┌─────────────────┐
    │ Public Site │      │   Customer   │     │  Admin Portal    │
    │  (Next.js)  │      │    Portal    │     │ (ERPNext Admin)  │
    │             │      │  (Next.js)   │     │                  │
    │ opentra.    │      │ portal.      │     │ admin.           │
    │ opentech.sa │      │ opentra.     │     │ opentra.         │
    │             │      │ opentech.sa  │     │ opentech.sa      │
    └──────┬──────┘      └──────┬───────┘     └────────┬─────────┘
           │                    │                      │
           │ Signup API         │ OAuth2 + REST        │ Internal UI
           │                    │                      │
           ▼                    ▼                      ▼
    ┌──────────────────────────────────────────────────────────┐
    │              ADMIN SERVER (Existing)                      │
    │              ─────────────────────────                    │
    │   • ERPNext for internal company operations               │
    │   • Frappe App: opentra_admin                             │
    │       - DocTypes: Customer, Subscription, Feature,        │
    │                   Site, Support Ticket, Activation Log    │
    │       - Public Signup API                                 │
    │       - Internal Provisioning Orchestrator                │
    │       - OAuth2 Provider (for Customer Portal auth)        │
    │   • Issues tax invoices (ZATCA-compliant)                 │
    │   • HR + Payroll for Opentra employees                    │
    └───────────────────────┬──────────────────────────────────┘
                            │
                            │ Internal API (mTLS + JWT signed)
                            │ POST /api/provision
                            │ POST /api/feature/activate
                            │ POST /api/feature/deactivate
                            │ POST /api/site/suspend
                            │ GET  /api/site/status
                            │
                            ▼
    ┌──────────────────────────────────────────────────────────┐
    │              CUSTOMER SERVER (Existing)                   │
    │              ────────────────────────                     │
    │   • Hetzner Ubuntu 22.04, 77.42.75.231                    │
    │   • Frappe Bench with multi-tenant sites                  │
    │   • Flask Provisioning API (port 5000)                    │
    │                                                            │
    │   • Shared Apps installed on all sites:                   │
    │       - frappe, erpnext, zatca_integration                │
    │       - opentra_core (Opentra core infrastructure)        │
    │                                                            │
    │   • Optional Apps (installed per subscription):           │
    │       - opentra_retention                                 │
    │       - opentra_hr_premium                                │
    │       - opentra_payroll_ksa                               │
    │       - opentra_manufacturing                             │
    │       - opentra_pos                                       │
    │       - etc.                                              │
    │                                                            │
    │   • Sites:                                                │
    │       demo.opentra.opentech.sa     (public demo)          │
    │       <customer1>.opentra.opentech.sa                     │
    │       <customer2>.opentra.opentech.sa                     │
    │       ...                                                 │
    └──────────────────────────────────────────────────────────┘
```

### 3.2 المبادئ المعمارية / Architectural Principles

1. **Separation of Control Plane and Data Plane**
   - Admin Server = Control Plane (business logic, billing, orchestration)
   - Customer Server = Data Plane (customer data, ERPNext sites)
   - أي اختراق في أحدهما لا يعرّض الآخر للخطر

2. **Single Source of Truth**
   - كل subscription له مصدر واحد موثوق: `Opentra Subscription` DocType على Admin Server
   - Customer Server يستقبل الحالة من Admin Server ولا يحفظ business state مستقل

3. **Idempotent Operations**
   - كل API call يمكن إعادته بأمان دون آثار جانبية
   - Feature activation/deactivation تتحقق من الحالة الحالية قبل التنفيذ

4. **Feature as a Package**
   - كل ميزة مدفوعة = Frappe App منفصل
   - install/uninstall عبر `bench install-app` / `bench uninstall-app`
   - نظيف، قابل للترقية، قابل للاختبار

5. **Graceful Degradation**
   - إذا فشل اتصال Admin Server ↔ Customer Server، العميل يستمر في استخدام موقعه
   - الـ sync يُعاد عند استعادة الاتصال

6. **Security First**
   - Internal API محمي بـ mTLS + JWT
   - Customer passwords لا تمر عبر Admin Server إلا مشفّرة
   - Secrets في Vault (أو ملفات بصلاحيات صارمة في البداية)
