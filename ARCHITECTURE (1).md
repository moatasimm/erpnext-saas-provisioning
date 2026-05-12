# Opentra SaaS — وثيقة المعمارية الرسمية

> **الإصدار:** 1.0 — معتمد  
> **آخر تحديث:** مايو 2026  
> **المؤلفون:** Moatasim Almalki + Claude  
> **الحالة:** ✅ معتمد — جاهز للتنفيذ

---

## فهرس المحتويات

1. [الرؤية والنموذج التجاري](#1-الرؤية-والنموذج-التجاري)
2. [تحليل السوق والمنافسين](#2-تحليل-السوق-والمنافسين)
3. [المعمارية عالية المستوى](#3-المعمارية-عالية-المستوى)
4. [الأنظمة الثلاثة تفصيلاً](#4-الأنظمة-الثلاثة-تفصيلاً)
5. [البوابات الثلاث](#5-البوابات-الثلاث)
6. [نموذج التسعير الديناميكي](#6-نموذج-التسعير-الديناميكي)
7. [دورة حياة العميل](#7-دورة-حياة-العميل)
8. [Provisioning Lifecycle](#8-provisioning-lifecycle)
9. [القرارات التقنية المعتمدة](#9-القرارات-التقنية-المعتمدة)
10. [خطة العمل — Roadmap](#10-خطة-العمل--roadmap)
11. [تحليل التكاليف](#11-تحليل-التكاليف)
12. [المبادئ المعمارية](#12-المبادئ-المعمارية)

---

## 1. الرؤية والنموذج التجاري

### 1.1 الرؤية

**Opentra** منصة SaaS تقدم ERPNext كخدمة مُدارة بالكامل للشركات الصغيرة والمتوسطة في **المملكة العربية السعودية ودول الخليج والأردن**، مع تكامل كامل مع ZATCA (Phase 1 & 2) وتخصيصات صناعية مخصصة.

النموذج التجاري قائم على **Modular Subscriptions** — العميل يختار الميزات التي يحتاجها فقط ويدفع بناءً على اختياره، مع إمكانية الإضافة أو الإزالة في أي وقت.

### 1.2 الأسواق المستهدفة

| السوق | الأولوية | ملاحظة |
|-------|----------|--------|
| 🇸🇦 المملكة العربية السعودية | Primary | ZATCA Phase 1 & 2 |
| 🇰🇼 الكويت | Secondary | |
| 🇦🇪 الإمارات | Secondary | |
| 🇶🇦 قطر | Secondary | |
| 🇧🇭 البحرين | Secondary | |
| 🇴🇲 عُمان | Secondary | |
| 🇯🇴 الأردن | Secondary | |

### 1.3 العميل المثالي (ICP)

شركة صغيرة-متوسطة سعودية أو خليجية:
- **الحجم:** 5–100 موظف
- **القطاع:** مقاولات، تجزئة، خدمات، تصنيع
- **الميزانية:** 500–5,000 SAR/شهر
- **الحاجة:** ERP حقيقي + ZATCA + دعم عربي محلي + بدون IT team داخلي

---

## 2. تحليل السوق والمنافسين

### 2.1 خريطة المنافسين

| المنافس | النوع | نقاط القوة | نقاط الضعف | السعر التقريبي |
|---------|-------|------------|------------|----------------|
| **Odoo Online** | ERP عالمي | قوي ومعروف | لا ZATCA native، لا عربي حقيقي | ~$24–80/user |
| **Qoyod** | محاسبة سعودية | ZATCA، واجهة جميلة | محاسبة فقط، لا ERP | 150–500 SAR/شهر |
| **Wafeq** | محاسبة سعودية | ZATCA Phase 2، سهل | محاسبة فقط، لا ERP | 99–499 SAR/شهر |
| **Daftra** | فواتير | عربي، GCC | محاسبة فقط | 50–300 SAR/شهر |
| **Zoho One** | Suite عالمي | شامل | لا ZATCA، لا تخصيص | ~$37/user |
| **SAP BC** | Enterprise | موثوق جداً | غالٍ جداً، معقد | 1,000+ SAR/user |
| **Microsoft D365** | Enterprise | تكامل Office | غالٍ، يحتاج خبراء | 800+ SAR/user |

### 2.2 الفرصة التنافسية (Gap Analysis)

```
السوق يفتقر إلى مزيج واحد يجمع:
┌─────────────────────────────────────────────────────────┐
│  ✅ ERP كامل (ليس محاسبة فقط)                          │
│  ✅ ZATCA Phase 1 & 2 built-in                          │
│  ✅ تسعير modular — ادفع ما تحتاج فقط                  │
│  ✅ تخصيصات صناعية (مقاولات، تجزئة، تصنيع)             │
│  ✅ Data isolation حقيقية — لا shared database          │
│  ✅ دعم عربي محلي + SLA                                 │
│  ✅ أرخص من SAP/D365 بـ 70–80%                         │
└─────────────────────────────────────────────────────────┘
                    = Opentra
```

### 2.3 الميزة التنافسية الأساسية

**Retention App (opentra_retention)** — مثال حي على قوة النهج الصناعي:
- صناعة المقاولات في السعودية تتعامل بالـ retention بنسبة 5–10% من كل فاتورة
- لا يوجد نظام سعودي/خليجي يعالج هذا المحاسبياً بشكل صحيح
- Opentra تتعامل معه بـ 4 journal entries آلية وتقرير كامل

---

## 3. المعمارية عالية المستوى

### 3.1 نظرة عامة — 3 أنظمة + 3 بوابات

```
═══════════════════════════════════════════════════════════════════════
                              INTERNET
═══════════════════════════════════════════════════════════════════════
          │                       │                        │
          ▼                       ▼                        ▼
  ┌───────────────┐     ┌──────────────────┐    ┌──────────────────┐
  │  SYSTEM 1     │     │    SYSTEM 2      │    │    SYSTEM 3      │
  │  Admin Portal │     │ Customer Portal  │    │ Customer Server  │
  │               │     │   (Next.js)      │    │   (Hetzner)      │
  │ erp.opentech  │     │opentra.opentech  │    │ 77.42.75.231     │
  │ .sa           │     │.sa               │    │                  │
  │ 45.90.220.57  │     │                  │    │ frappe-bench/    │
  │               │     │ ┌─────────────┐  │    │ ├── demo.*       │
  │ ERPNext       │     │ │  Portal A   │  │    │ ├── client1.*    │
  │ + opentra_    │     │ │  (Public)   │  │    │ ├── client2.*    │
  │   admin app   │     │ │  Landing    │  │    │ └── clientN.*    │
  │               │     │ │  Pricing    │  │    │                  │
  │ يدير:         │     │ │  Signup     │  │    │ Flask API :5000  │
  │ • العملاء     │     │ │  Payment    │  │    │ (Provisioning)   │
  │ • الاشتراكات  │     │ └─────────────┘  │    │                  │
  │ • الفواتير    │     │ ┌─────────────┐  │    │                  │
  │ • Tickets     │     │ │  Portal B   │  │    │                  │
  │ • Backups     │     │ │  (Private)  │  │    │                  │
  │ • التسعير     │     │ │  Dashboard  │  │    │                  │
  │ • Analytics   │     │ │  Self-svc   │  │    │                  │
  └───────┬───────┘     └──────┬───────┘    └──────────┬───────────┘
          │                    │                        │
          │◄───────────────────┘  Auth API + Signup     │
          │                                             │
          └─────────────────────────────────────────────►
                     Internal Provisioning API
                     (HTTPS + JWT signed, port 5000)
```

### 3.2 فصل الطبقات (Separation of Concerns)

| الطبقة | النظام | المسؤولية |
|--------|--------|-----------|
| **Control Plane** | System 1 (Admin) | Business logic، billing، orchestration، auth |
| **Customer Plane** | System 2 (Portal) | UX للعميل، self-service، support |
| **Data Plane** | System 3 (Hetzner) | بيانات العملاء، ERPNext sites |

> أي اختراق في طبقة لا يعرّض الطبقات الأخرى للخطر.

---

## 4. الأنظمة الثلاثة تفصيلاً

### 4.1 System 1 — Admin Portal (`erp.opentech.sa`)

نظام **موجود ويعمل** على `45.90.220.57`. نضيف عليه Frappe App جديد: `opentra_admin`.

#### DocTypes الجديدة (opentra_admin)

```
opentra_admin/
├── Opentra Client              ← بيانات كل عميل (site URL, status, plan, company info)
├── Opentra Subscription        ← الاشتراك الحالي + تاريخ التجديد + الميزات المفعّلة
├── Opentra Feature             ← كتالوج الميزات المتاحة + تسعيرها + اسم الـ app
├── Opentra Pricing Plan        ← الخطط (Starter, Growth, Business, Enterprise)
├── Opentra Discount Rule       ← قواعد الخصم (سنوي، promo، volume)
├── Opentra Currency Pricing    ← تسعير يدوي لكل (plan/feature × currency)
├── Opentra Tax Invoice         ← الفواتير الضريبية ZATCA-compliant للعملاء
├── Opentra Support Ticket      ← تذاكر الدعم المستقبَلة من Portal B
├── Opentra Backup Log          ← سجل كل عمليات backup/restore لكل عميل
├── Opentra Provisioning Log    ← سجل كل عمليات إنشاء/تعديل/حذف sites
└── Opentra Service Catalog     ← خدمات إضافية (training, migration, custom dev)
```

#### الشاشات المطلوبة بناؤها

| الشاشة | الوصف | الأولوية |
|--------|-------|----------|
| **Clients Dashboard** | Overview كل العملاء + status + إحصائيات | Phase 1 |
| **Client Profile** | تفاصيل عميل + subscription + site status + invoices | Phase 1 |
| **Backup Management** | backup/restore لكل عميل بزرار + سجل + مساحة | Phase 1 |
| **Support Tickets** | استقبال + تصنيف + رد + إغلاق | Phase 1 |
| **Pricing Manager** | تعديل الأسعار والخطط من الواجهة | Phase 1 |
| **Feature Catalog** | إدارة الميزات المتاحة وتفعيلها | Phase 1 |
| **Provisioning Panel** | إنشاء/إيقاف/حذف sites يدوياً | Phase 1 |
| **Revenue Analytics** | MRR, ARR, Churn, Growth charts | Phase 2 |
| **ZATCA Invoicing** | إصدار فواتير ضريبية للعملاء | Phase 2 |

### 4.2 System 2 — Customer Portal (`opentra.opentech.sa`)

Next.js 15 App Router — تفصيل كامل في [القسم 5](#5-البوابات-الثلاث).

### 4.3 System 3 — Customer Server (`77.42.75.231`)

#### هيكل frappe-bench

```
/home/frappe/frappe-bench/
├── apps/
│   ├── frappe                  ← core framework (mandatory)
│   ├── erpnext                 ← ERP base (mandatory)
│   ├── zatca_integration       ← ZATCA Phase 1 & 2 (mandatory للسعودية)
│   ├── opentra_core            ← Opentra infrastructure (mandatory)
│   │   ├── Customer Portal User DocType
│   │   ├── Customer Portal Tenant DocType
│   │   └── shared API helpers
│   │
│   ├── opentra_retention       ← ✅ v0.1.0 مكتمل ومختبر
│   ├── opentra_hr_premium      ← مخطط
│   ├── opentra_payroll_ksa     ← مخطط (GOSI integration)
│   ├── opentra_payroll_gcc     ← مخطط
│   ├── opentra_pos             ← مخطط
│   ├── opentra_manufacturing   ← مخطط
│   ├── opentra_warehouse       ← مخطط
│   ├── opentra_projects        ← مخطط
│   └── opentra_reports         ← مخطط (custom reports pack)
│
├── sites/
│   ├── demo.opentra.opentech.sa        ← demo عام (reset يومي آلي)
│   ├── {client1}.opentra.opentech.sa   ← قاعدة بيانات مستقلة
│   ├── {client2}.opentra.opentech.sa   ← قاعدة بيانات مستقلة
│   └── ...
│
└── provisioning-api/                   ← Flask API (port 5000)
    ├── POST /provision                 ← إنشاء site جديد كامل
    ├── POST /install-feature           ← تثبيت Frappe app
    ├── POST /remove-feature            ← إزالة Frappe app
    ├── POST /backup                    ← إنشاء backup → رفع لـ R2
    ├── POST /restore                   ← استعادة backup من R2
    ├── POST /suspend                   ← تعليق الموقع (read-only)
    ├── POST /activate                  ← تفعيل الموقع
    ├── DELETE /site                    ← حذف نهائي بعد Grace Period
    └── GET /status/{site}              ← حالة الموقع + disk + users
```

#### Feature كـ Package — المبدأ الأساسي

```
كل ميزة مدفوعة = Frappe App مستقل:

bench install-app opentra_retention      ← تفعيل الميزة
bench uninstall-app opentra_retention    ← إلغاء الميزة

✅ نظيف معمارياً
✅ قابل للترقية المستقلة
✅ قابل للاختبار بمعزل
✅ لا coupling بين الميزات
```

---

## 5. البوابات الثلاث

### 5.1 Portal A — العامة (قبل Login)

**الهدف:** تحويل الزائر إلى مشترك مدفوع بأقل احتكاك.

```
opentra.opentech.sa/
├── /                   Landing Page
│   ├── Hero + Value Proposition
│   ├── Industry Solutions (مقاولات، تجزئة، تصنيع)
│   ├── Customer Logos + Testimonials
│   └── CTA → التجربة المجانية
│
├── /features           صفحة الميزات
│   ├── Modules (Accounting, HR, CRM, ...)
│   ├── Services (Retention, ZATCA, Backup, ...)
│   └── مقارنة بالمنافسين
│
├── /pricing            حاسبة التسعير التفاعلية
│   ├── اختر خطتك الأساسية
│   ├── أضف الميزات التي تحتاجها (drag & add)
│   ├── اختر عدد المستخدمين
│   ├── شهري / سنوي toggle (+ خصم سنوي)
│   ├── السعر يتحدث لحظياً
│   └── CTA → ابدأ التجربة المجانية
│
├── /demo               Redirect → demo.opentra.opentech.sa
│
├── /signup             تسجيل جديد
│   ├── Step 1: بيانات الشركة + المسؤول
│   ├── Step 2: اختيار الخطة + الميزات (pre-filled من pricing)
│   ├── Step 3: الدفع (Moyasar)
│   └── Step 4: Provisioning + confirmation email
│
├── /about              عن الشركة
├── /contact            تواصل / Enterprise Quote Form
└── /blog               محتوى تسويقي (SEO)
```

### 5.2 Portal B — الخاصة (بعد Login)

**الهدف:** العميل يدير اشتراكه بالكامل بدون تواصل مع الدعم.

```
/dashboard              نظرة عامة
│   ├── حالة الموقع (Online/Offline + Uptime)
│   ├── تفاصيل الاشتراك (الخطة + تاريخ التجديد)
│   ├── المساحة المستخدمة (storage gauge)
│   ├── عدد المستخدمين النشطين
│   └── آخر backup + حالته
│
├── /subscription       إدارة الاشتراك
│   ├── الخطة الحالية + Upgrade / Downgrade
│   ├── الميزات المفعّلة + إضافة/إزالة
│   ├── عدد المستخدمين + زيادة/تقليل
│   └── تغيير دورة الدفع (شهري ↔ سنوي)
│
├── /billing            الفوترة والدفع
│   ├── الفاتورة الحالية + تاريخ الاستحقاق
│   ├── سجل الفواتير السابقة (download PDF)
│   ├── طريقة الدفع المحفوظة
│   └── تحديث بيانات الدفع
│
├── /backup             النسخ الاحتياطية
│   ├── زر "إنشاء Backup الآن" (بزرار واحد)
│   ├── جدول النسخ الاحتياطية الآلية
│   ├── قائمة النسخ المحفوظة + التاريخ + الحجم
│   ├── زر "Restore" لكل نسخة (مع تأكيد)
│   └── مؤشر المساحة المستخدمة
│
├── /monitoring         المراقبة
│   ├── Uptime chart (آخر 30 يوم)
│   ├── استخدام المساحة (trend)
│   ├── عدد المستخدمين النشطين (trend)
│   └── آخر 10 أحداث في النظام
│
├── /support            الدعم الفني
│   ├── فتح تذكرة جديدة (مع screenshots)
│   ├── قائمة التذاكر المفتوحة
│   ├── سجل التذاكر المغلقة
│   └── Live Chat (Crisp widget)
│
└── /settings           الإعدادات
    ├── بيانات الشركة
    ├── تغيير كلمة المرور
    ├── إعدادات الإشعارات (Email/SMS/WhatsApp)
    └── طلب حذف الحساب
```

### 5.3 Admin Portal — الشاشات الإضافية (`erp.opentech.sa`)

راجع [القسم 4.1](#41-system-1--admin-portal-erpopentech).

---

## 6. نموذج التسعير الديناميكي

### 6.1 المبدأ

التسعير **ديناميكي بالكامل** — يُدار من Admin Panel عبر DocTypes قابلة للتعديل دون تغيير في الكود.

### 6.2 الخطط الأساسية

| Plan | Users | Storage | الوصف |
|------|-------|---------|-------|
| **Starter** | 3 | 5 GB | للشركات الناشئة |
| **Growth** | 10 | 20 GB | للشركات النامية |
| **Business** | 25 | 50 GB | للشركات المتوسطة |
| **Enterprise** | Custom | Custom | Custom Quote |

> الأسعار قيم في قاعدة البيانات — تُعدَّل من Admin Panel دون لمس الكود.

### 6.3 كتالوج الميزات

| الميزة | Technical Name | نموذج التسعير |
|--------|---------------|--------------|
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

### 6.4 نماذج التسعير

| النموذج | الوصف | مثال |
|---------|-------|------|
| `flat` | سعر ثابت شهري | Retention = 50 SAR/شهر |
| `per_user` | سعر لكل مستخدم | HR = 10 SAR/user/شهر |
| `per_transaction` | سعر لكل معاملة | ZATCA = 0.5 SAR/فاتورة |
| `tiered` | شرائح تنازلية | 1–10 users بـ X، 11–50 بـ Y |

### 6.5 الخصومات

| نوع الخصم | الوصف |
|-----------|-------|
| `billing_cycle` | خصم الدفع السنوي (افتراضي 15%) |
| `promo_code` | كود ترويجي (LAUNCH20 = 20%) |
| `min_features` | 3+ ميزات = خصم إضافي |
| `customer_group` | شركات ناشئة، NGO، إلخ |
| `volume_users` | 50+ users = خصم حجم |

### 6.6 العملات المدعومة

SAR (Primary), AED, KWD, QAR, BHD, OMR, JOD, USD

**المنهجية:** تسعير يدوي لكل عملة (ليس تحويل تلقائي) — يمنع تقلبات الصرف ويتيح التسعير النفسي.

---

## 7. دورة حياة العميل

```
زائر جديد
    │
    ▼
[Portal A] يستكشف الميزات → يجرب الحاسبة → يختار خطته
    │
    ▼
[Signup] بيانات الشركة + اختيار الميزات
    │
    ▼
[Payment] Moyasar (mada, Visa, STC Pay, Apple Pay)
    │
    ├── ❌ فشل الدفع → يبقى في signup مع رسالة خطأ
    │
    ▼ ✅ نجح الدفع
[Auto-Provisioning] ← يبدأ خلال 60 ثانية
    │
    ▼
[Email] URL + credentials + دليل البدء (بالعربي)
    │
    ▼
[Trial Period] 14 يوم — استخدام كامل
    │
    ├── تجديد → Active Subscription
    ├── طلب تمديد → Extended Trial (30 يوم إضافي)
    └── عدم تجديد → Grace Period (30 يوم read-only + إشعارات)
                         │
                         └── انتهاء Grace → حذف نهائي
                             (إشعار قبل 7 أيام)
```

### مراحل الاشتراك

| المرحلة | المدة | الوصف | صلاحيات الموقع |
|---------|-------|-------|----------------|
| **Demo** | دائم | استكشاف بدون تسجيل، reset يومي | كاملة (بيانات وهمية) |
| **Trial** | 14 يوم | استخدام كامل بدون دفع | كاملة |
| **Extended Trial** | +30 يوم | عند الطلب للعملاء الجادين | كاملة |
| **Active** | حسب الاشتراك | مدفوع، شهري أو سنوي | كاملة |
| **Grace Period** | 30 يوم | عند عدم التجديد | read-only + export |
| **Suspended** | حتى الدفع | تعليق عند تأخر الدفع | لا دخول |
| **Deleted** | نهائي | بعد Grace Period | — |

> **قرار واعٍ:** لا Free Forever tier. العملاء المجانيون في B2B SaaS لا يتحولون عادةً إلى مدفوعين. Demo العام + Trial القوي يحققان نفس الغرض بتكلفة أقل.

---

## 8. Provisioning Lifecycle

### 8.1 Auto-Provisioning Flow (عند الدفع الناجح)

```
Moyasar Webhook → Admin Server (opentra_admin)
    │
    │ 1. تحقق من الدفع
    │ 2. أنشئ Opentra Client + Subscription
    │ 3. احجز subdomain: {company_slug}.opentra.opentech.sa
    │
    ▼
POST /api/provision → Customer Server (Flask :5000)
    │
    ├── bench new-site {site}
    │   └── --mariadb-root-password ***
    │       --admin-password {generated}
    │
    ├── bench --site {site} install-app frappe
    ├── bench --site {site} install-app erpnext
    ├── bench --site {site} install-app zatca_integration (إن SA)
    ├── bench --site {site} install-app opentra_core
    └── bench --site {site} install-app {feature_app} (لكل ميزة مشتركة)
    │
    ├── bench --site {site} execute setup.install.bootstrap
    │   └── إنشاء Company، Chart of Accounts، إعدادات أولية
    │
    ├── nginx: إضافة site إلى الـ wildcard config
    ├── bench restart
    │
    ▼
Admin Server: تحديث status = "Active"
    │
    ▼
Email Service: إرسال credentials + welcome guide
```

### 8.2 Feature Activation/Deactivation

```
POST /api/feature/activate
{site, app_name}
    │
    ├── bench --site {site} install-app {app_name}
    ├── bench --site {site} execute {app}.setup.install.after_install
    └── bench restart

POST /api/feature/deactivate
{site, app_name}
    │
    ├── [تحقق: هل البيانات قابلة للحذف الآمن؟]
    ├── bench --site {site} uninstall-app {app_name}
    └── bench restart
```

### 8.3 Backup Flow

```
POST /api/backup
{site}
    │
    ├── bench --site {site} backup --with-files
    │   └── ينتج: {timestamp}-{site}-database.sql.gz
    │              {timestamp}-{site}-files.tar
    │
    ├── rclone copy backup_files/ r2:opentra-backups/{site}/
    │
    ├── حذف النسخ الأقدم من 30 يوم على R2
    │
    └── Admin Server: تحديث Backup Log
```

---

## 9. القرارات التقنية المعتمدة

### 9.1 Payment Gateway — Moyasar ✅

| المعيار | القيمة |
|---------|--------|
| Setup cost | **0 SAR** |
| Monthly fixed | **0 SAR** |
| Visa/MC | 2.2% + 1 SAR |
| mada | 1.5% + 1 SAR |
| Recurring payments | ✅ الأول في SA يدعمه كاملاً |
| mada, STC Pay, Apple Pay | ✅ |
| SAMA licensed | ✅ |

**Upgrade Path:** عند التوسع لـ UAE/GCC → إضافة Tap Payments كـ secondary gateway بدون تغيير في الكود (Payment Gateway abstraction layer).

### 9.2 Authentication — JWT على Admin Server ✅

```
Customer Portal → POST /api/auth/login → Admin Server (erp.opentech.sa)
                ← JWT (24h) + Refresh Token (30d) في httpOnly cookie

كل request للـ Customer Server:
    Authorization: Bearer {JWT}
    X-Site-ID: {client_site}
    └── Customer Server يتحقق عبر shared secret
```

**Upgrade Path:** Keycloak self-hosted أو Auth0 لاحقاً — الـ API contracts لا تتغير.

### 9.3 Backup Storage — Cloudflare R2 ✅

| المرحلة | الحل | التكلفة |
|---------|------|---------|
| MVP (0–10 عملاء) | R2 Free Tier | **$0/شهر** |
| Growth (10–100) | R2 Paid | ~$7.5/شهر لـ 500GB |
| Scale (100+) | R2 (recent) + B2 (archive) | تخفيض 60% |

```python
# Abstraction من البداية — تغيير الـ backend بدون كسر الكود
class BackupStorage:
    def upload(self, file_path: str, key: str) -> bool: ...
    def download(self, key: str, dest: str) -> bool: ...
    def list(self, prefix: str) -> list[BackupFile]: ...
    def delete(self, key: str) -> bool: ...

# اليوم:
storage = R2BackupStorage(bucket="opentra-backups")
# غداً:
storage = HybridStorage(recent=R2(), archive=B2())
```

### 9.4 Monitoring — Uptime Kuma + Netdata ✅

```
الطبقة 1 — Uptime (External checks):
    Uptime Kuma (Docker على Hetzner server)
    ├── يراقب كل *.opentra.opentech.sa كل 60 ثانية
    ├── Status Page عام: status.opentra.opentech.sa
    ├── إشعارات: Telegram + Email
    └── API → Admin Portal يعرض status لكل عميل

الطبقة 2 — Server Metrics (Internal):
    Netdata (self-hosted)
    ├── CPU، RAM، Disk per site
    └── Real-time dashboards للـ Ops team

التكلفة: $0
Upgrade Path: Grafana Cloud (10K series مجاني) عند 50+ عميل
```

### 9.5 Support System — Crisp → Chatwoot ✅

```
Phase 1 — Crisp Free:
    ├── Live chat widget على Portal B
    ├── Email ticketing
    ├── 2 agents مجاني
    └── تكلفة: $0/شهر

Phase 2 — Chatwoot Self-hosted:
    ├── Docker على Hetzner (server موجود)
    ├── Unlimited agents
    ├── Email + Live Chat + WhatsApp + Telegram
    ├── API → تكامل مع Admin Portal
    └── تكلفة: $0/شهر

Phase 3 — Scale:
    └── Freshdesk/Zendesk عند 500+ ticket/شهر
```

### 9.6 Domain Pattern — Wildcard Subdomain ✅

```
Pattern: {client}.opentra.opentech.sa

SSL: Let's Encrypt Wildcard (certbot --dns)
    └── يغطي كل الـ subdomains تلقائياً
    └── تجديد آلي كل 90 يوم
    └── تكلفة: $0

nginx: server_name ~^(?<tenant>.+)\.opentra\.opentech\.sa$;
    └── ملف واحد يخدم كل العملاء
    └── لا إجراء يدوي عند إضافة عميل جديد

Premium Add-on (لاحقاً):
    └── Custom Domain: erp.clientcompany.com
        ├── العميل يضيف CNAME في DNS
        ├── certbot --nginx -d erp.clientcompany.com
        └── 50–100 SAR/شهر إضافي
```

---

## 10. خطة العمل — Roadmap

### Phase 0 — Foundation (أسبوعان)
**الهدف: وضع الأساس قبل البناء**

- [ ] تحديث ARCHITECTURE.md في GitHub (هذا الملف)
- [ ] تصميم DB Schema كامل لـ `opentra_admin` DocTypes
- [ ] إعداد Next.js project للـ Customer Portal
- [ ] تصميم API contracts بين الأنظمة الثلاثة
- [ ] إعداد Cloudflare R2 bucket + rclone config
- [ ] تثبيت Uptime Kuma على Hetzner

### Phase 1 — Admin Portal MVP (شهر 1–2)
**الهدف: فريق Opentech يدير العملاء بالكامل من Admin Portal**

- [ ] `opentra_admin` Frappe App على `erp.opentech.sa`
- [ ] Clients Dashboard (list + status + search + filter)
- [ ] Client Profile (subscription + site status + invoices)
- [ ] Provisioning Panel (إنشاء site يدوياً)
- [ ] Flask Provisioning API على Hetzner
- [ ] Backup/Restore Panel (بزرار)
- [ ] Support Tickets (استقبال + رد)
- [ ] Pricing Manager (تعديل الأسعار من الواجهة)

### Phase 2 — Customer Portal Public (شهر 2–3)
**الهدف: العميل يشترك بدون تدخل بشري**

- [ ] Landing Page + Features showcase
- [ ] Interactive Pricing Calculator
- [ ] Signup Flow (3 steps)
- [ ] Moyasar Payment Integration
- [ ] Auto-provisioning عند الدفع الناجح
- [ ] Email confirmation + credentials + welcome guide
- [ ] Demo site reset automation (يومي)

### Phase 3 — Customer Portal Private (شهر 3–4)
**الهدف: العميل يدير نفسه بالكامل**

- [ ] Login + JWT Auth
- [ ] Subscription Dashboard
- [ ] Upgrade/Downgrade Modules
- [ ] Self-service Backup/Restore
- [ ] Storage Monitoring
- [ ] Billing & Invoices
- [ ] Support Ticket System
- [ ] Crisp Live Chat integration

### Phase 4 — Automation & Intelligence (شهر 4–6)
**الهدف: المنصة تدير نفسها**

- [ ] Auto-renewal + Auto-suspension
- [ ] Grace Period automation
- [ ] Monitoring & Alerts (uptime, disk thresholds)
- [ ] Revenue Analytics Dashboard (MRR, Churn, LTV)
- [ ] ZATCA invoicing للعملاء من Admin Portal
- [ ] Multi-currency pricing
- [ ] SMS/WhatsApp notifications
- [ ] Chatwoot self-hosted migration

### Phase 5 — Growth (شهر 6+)
- [ ] Affiliate/Referral Program
- [ ] Enterprise Quote Flow
- [ ] Custom Domain add-on
- [ ] Tap Payments (توسع GCC)
- [ ] White-label option
- [ ] API للتكامل الخارجي
- [ ] Mobile App (React Native)

---

## 11. تحليل التكاليف

### التكاليف الثابتة الشهرية

| المكوّن | MVP (0–10) | Growth (10–100) | Scale (100+) |
|---------|-----------|-----------------|--------------|
| Payment Gateway | 0 SAR | 0 SAR | 0 SAR |
| Backup Storage | 0 SAR | ~30 SAR | ~150 SAR |
| Monitoring | 0 SAR | 0 SAR | 0–75 SAR |
| Support System | 0 SAR | 0 SAR | 0–300 SAR |
| Auth | 0 SAR | 0 SAR | 0 SAR |
| SSL | 0 SAR | 0 SAR | 0 SAR |
| **المجموع** | **0 SAR** | **~30 SAR** | **~525 SAR** |

> Infrastructure (Hetzner + Admin Server) موجود مسبقاً — لا تكلفة إضافية.

### التكاليف المتغيرة

- Payment processing: 2.2% + 1 SAR لكل معاملة (Moyasar)
- Storage إضافي للعملاء: $15/TB (Cloudflare R2)
- Custom domain add-on: تكلفة SSL renewal فقط (~0)

### Break-even Analysis

```
إذا كان متوسط الاشتراك = 500 SAR/شهر:
    عمولة Moyasar = (500 × 2.2%) + 1 = 12 SAR
    صافي لكل عميل = 488 SAR/شهر

عند 10 عملاء:
    إيراد = 5,000 SAR/شهر
    تكاليف متغيرة = 120 SAR
    تكاليف ثابتة إضافية = 0 SAR
    هامش = 4,880 SAR/شهر (97.6%)
```

---

## 12. المبادئ المعمارية

### 1. Separation of Control & Data Planes
Admin Server = Control (business logic، billing)  
Customer Server = Data (بيانات العملاء)  
اختراق أحدهما لا يعرّض الآخر للخطر.

### 2. Single Source of Truth
`Opentra Subscription` على Admin Server هو المصدر الوحيد الموثوق.  
Customer Server يستقبل الحالة ولا يحفظ business state مستقل.

### 3. Idempotent Operations
كل API call يمكن إعادته بأمان. Feature activation تتحقق من الحالة قبل التنفيذ.

### 4. Feature as a Package
كل ميزة = Frappe App مستقل. Install/uninstall نظيف وقابل للترقية المستقلة.

### 5. Abstraction Over Implementation
جميع الـ external dependencies (storage، payments، notifications) خلف interfaces.  
تغيير الـ provider = تغيير implementation واحد بدون كسر.

### 6. Zero Vendor Lock-in at MVP
لا اشتراكات ثابتة مكلفة في المراحل الأولى.  
كل اختيار قابل للتبديل بتكلفة هجرة منخفضة.

### 7. Graceful Degradation
إذا فشل اتصال Admin ↔ Customer، العميل يستمر في استخدام موقعه.  
الـ sync يُعاد عند استعادة الاتصال.

### 8. Security First
- Internal API: HTTPS + JWT signed (shared secret)
- Customer passwords: لا تُخزَّن على Admin Server
- Backup files: encrypted at rest على R2
- Wildcard SSL: Let's Encrypt، تجديد آلي

---

## Appendix A — Tech Stack الكامل

| Layer | Technology | الاستخدام |
|-------|-----------|----------|
| **Backend (Admin)** | Frappe/ERPNext | Admin Portal + opentra_admin app |
| **Backend (Customer Sites)** | Frappe/ERPNext | ERPNext sites للعملاء |
| **Provisioning API** | Flask (Python) | Internal API على Hetzner |
| **Customer Portal** | Next.js 15 (App Router) | Portal A + Portal B |
| **Language** | TypeScript (strict) | Customer Portal |
| **Styling** | Tailwind CSS + shadcn/ui | Customer Portal |
| **State Management** | TanStack Query | API calls + caching |
| **Validation** | Zod | Runtime API response validation |
| **RTL Support** | `dir="rtl"` + Tailwind RTL | Arabic interface |
| **Font** | IBM Plex Sans Arabic | Arabic typography |
| **Payment** | Moyasar | مدفوعات SA |
| **Backup Storage** | Cloudflare R2 | S3-compatible، zero egress |
| **Monitoring** | Uptime Kuma + Netdata | Uptime + server metrics |
| **Support** | Crisp → Chatwoot | Live chat + ticketing |
| **Email** | Frappe Email (SMTP) | Transactional emails |
| **SSL** | Let's Encrypt Wildcard | certbot --dns |
| **Web Server** | nginx | Reverse proxy |
| **OS** | Ubuntu 22.04 | Hetzner + Admin Server |

---

## Appendix B — Feature Apps Status

| App | Status | Version | الوصف |
|-----|--------|---------|-------|
| `opentra_retention` | ✅ مكتمل ومختبر | 0.1.0 | Payment Retention للمقاولات |
| `opentra_core` | 🔄 مخطط | — | Portal DocTypes + shared APIs |
| `opentra_hr_premium` | 📋 في القائمة | — | HR متقدم |
| `opentra_payroll_ksa` | 📋 في القائمة | — | رواتب + GOSI |
| `opentra_zatca_premium` | 📋 في القائمة | — | ZATCA Phase 2 متكامل |
| `opentra_pos` | 📋 في القائمة | — | نقاط البيع |
| `opentra_manufacturing` | 📋 في القائمة | — | التصنيع |
| `opentra_reports` | 📋 في القائمة | — | تقارير مخصصة |

---

*وثيقة معتمدة — أي تعديل يمر عبر ADR (Architecture Decision Record)*  
*آخر تحديث: مايو 2026*
