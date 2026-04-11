# Opentra SaaS — Decisions Log

> **Purpose:** ملخص مختصر جداً لكل القرارات المعمارية المحسومة. يُقرأ في بداية كل جلسة جديدة لاستعادة السياق بسرعة.
>
> **آخر تحديث:** 11 أبريل 2026

---

## ✅ القرارات المحسومة (14 قرار)

### المنتج
1. **الاسم:** Opentra
2. **النطاق الأساسي:** `opentra.opentech.sa`
3. **الأسواق:** السعودية (أولاً) + خليج + الأردن
4. **اللغات:** عربي + إنجليزي في كل شيء

### البوابات والنطاقات
5. **Public Site:** `opentra.opentech.sa` — Next.js 15 + Tailwind + shadcn/ui + Framer Motion
6. **Customer Portal:** `portal.opentra.opentech.sa` — نفس Stack
7. **Admin Panel:** `admin.opentra.opentech.sa` — Frappe app `opentra_admin` على Admin Server (ERPNext الداخلي)
8. **Demo:** `demo.opentra.opentech.sa` — موقع عام، مقاولات، reset يومي
9. **مواقع العملاء:** `<customer>.opentra.opentech.sa`

### البنية التحتية
10. **Customer Server:** Hetzner 77.42.75.231 — Frappe bench متعدد المواقع (موجود)
11. **Admin Server:** ERPNext داخلي للشركة الأم (موجود، سنضيف `opentra_admin` app عليه)
12. **Provisioning API:** Flask على Customer Server port 5000 (موجود)

### الأمان والمصادقة
13. **Internal API (Admin ↔ Customer Server):** JWT signed + mTLS
14. **Customer Auth:** OAuth2 (Admin Server = provider)

### النموذج التجاري
- **Pricing:** ديناميكي بالكامل من Admin Panel (DocTypes، بدون hardcoding)
- **Pricing Models:** flat / per_user / per_transaction / tiered
- **Currencies:** SAR + AED + KWD + QAR + BHD + OMR + JOD + USD (تسعير يدوي لكل عملة)
- **Free Tier:** ❌ لا يوجد
- **Trial:** 14 يوم + extended 30 يوم عند الطلب
- **Grace Period:** 30 يوم بعد انتهاء الاشتراك (read-only)
- **Deletion:** بعد grace period
- **Enterprise:** Custom Quote عبر فورم → `Opentra Lead` DocType

### الميزات المدفوعة (الخطة الأولية)
كل ميزة = Frappe App منفصل:
- `opentra_retention` (أول ميزة — سيُعاد بناؤه من الصفر)
- `opentra_hr_premium`
- `opentra_payroll_ksa`
- `opentra_payroll_gcc`
- `opentra_zatca_premium`
- `opentra_reports`
- `opentra_pos`
- `opentra_manufacturing`
- `opentra_warehouse`
- `opentra_projects`

### DocTypes الـ Pricing Engine (على Admin Server)
1. `Opentra Pricing Plan`
2. `Opentra Feature`
3. `Opentra User Pricing Tier`
4. `Opentra Storage Pricing`
5. `Opentra Discount Rule`
6. `Opentra Pricing Settings` (Single)
7. `Opentra Currency Pricing`
8. `Opentra Lead` (Enterprise quotes)

---

## 🎯 الأولويات للجلسة القادمة

### Section 4: تفاصيل المكونات
- `opentra_admin` (Admin Server)
- `opentra_core` (Customer Server — يُثبَّت على كل المواقع)
- `opentra_retention` (أول ميزة مدفوعة — إعادة بناء كامل)
- Public Site (Next.js)
- Customer Portal (Next.js)

### Section 5: DocTypes Schemas (الأهم)
الكامل لكل DocType مع:
- Fields (name, type, required, options)
- Child Tables
- Naming series
- Permissions
- Workflows
- Custom scripts إن وُجدت

### Section 6: API Contracts
كل endpoint مع:
- Request/Response schemas
- Authentication
- Rate limiting
- Error codes

### Section 7: Security Model
- mTLS setup بين السيرفرين
- JWT signing keys management
- OAuth2 flow الكامل
- Secrets management
- Backup encryption

### Section 8: Deployment Plan
- CI/CD pipeline
- How to deploy `opentra_admin`
- How to deploy `opentra_core` to all customer sites
- How to deploy new features
- Rollback strategy

### Section 9: Milestones & Roadmap
- Sprint 1: `opentra_core` foundation
- Sprint 2: `opentra_admin` DocTypes + Pricing Engine
- Sprint 3: Public Site (signup flow)
- Sprint 4: Customer Portal
- Sprint 5: `opentra_retention` (rebuild)
- Sprint 6: Polish + Soft Launch

---

## 🔴 مشاكل معروفة يجب إصلاحها

### Retention الحالي معيوب محاسبياً
- GL entries ترمي Retention Payable في الجانب المدين بدلاً من الدائن
- `outstanding_amount` يشمل retention بدلاً من خصمه
- لا يوجد Release workflow
- **القرار:** إعادة بناء كامل في `opentra_retention` app (جلسة مخصصة)

### Jobs في Flask API لا تُشارَك بين workers
- Provisioning API يستخدم gunicorn بـ 2 workers و `jobs` dict محلي
- `/api/site/status` أحياناً يعيد "Job not found" إذا وصل لـ worker مختلف
- **الحل:** نقل jobs لـ Redis (مؤجَّل، low priority)

### `opentra_admin` غير موجود بعد
- يجب إنشاء أول Frappe app على Admin Server
- يجب إعداد الربط الآمن مع Customer Server

---

## 📝 ملاحظات للجلسة القادمة

1. **ابدأ بقراءة هذا الملف + `ARCHITECTURE.md` من GitHub** لاستعادة السياق
2. **أول عمل برمجي فعلي:** إنشاء Frappe app جديد `opentra_admin` على Admin Server
3. **ثاني عمل:** إنشاء DocTypes الأساسية للـ Pricing Engine في `opentra_admin`
4. **ثالث عمل:** API endpoints العامة للـ Pricing (لاستخدامها من Public Site)

---

## 📚 مراجع مفيدة

- [Frappe Documentation](https://frappeframework.com/docs)
- [ERPNext Documentation](https://docs.erpnext.com)
- [ZATCA Developer Portal](https://zatca.gov.sa)
- [Next.js 15 Docs](https://nextjs.org/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
