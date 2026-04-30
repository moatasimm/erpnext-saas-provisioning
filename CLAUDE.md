# Opentra SaaS — Claude Context File
> هذا الملف يُقرأ تلقائياً من Claude Code، ويُرسَل يدوياً في بداية كل جلسة Claude.ai

---

## 🏢 المشروع

**Opentra** — منصة ERPNext SaaS للسوق السعودي والخليجي  
**الشركة:** OpenTech (`opentech.sa`)  
**GitHub:** https://github.com/moatasimm/erpnext-saas-provisioning  
**الأسواق:** السعودية (أولاً) → الخليج → الأردن  
**اللغات:** عربي + إنجليزي في كل شيء

---

## 🖥️ البنية التحتية

| السيرفر | IP | الدور | الـ Stack |
|---|---|---|---|
| Customer Server | `77.42.75.231` | مواقع العملاء | Frappe v15.103 + ERPNext v15.102 + zatca_integration |
| Admin Server | `45.90.220.57` | ERPNext الداخلي | Frappe v15.100 + ERPNext v15.98 + HR + KSA Compliance v0.60 |

**Provisioning API:** Flask على Customer Server port `5000`  
**Admin Panel URL:** `erp.opentech.sa`  
**Customer Sites Pattern:** `<subdomain>.opentra.opentech.sa`

---

## 🌐 الدومينات والبوابات

| البوابة | URL | Stack | الحالة |
|---|---|---|---|
| Public Site | `opentra.opentech.sa` | Next.js 15 + Tailwind + shadcn/ui | لم يُبنَ |
| Customer Portal | `portal.opentra.opentech.sa` | Next.js 15 | لم يُبنَ |
| Admin Panel | `admin.opentra.opentech.sa` | Frappe app `opentra_admin` | لم يُبنَ |
| Demo Site | `demo.opentra.opentech.sa` | ERPNext + reset يومي | لم يُبنَ |

---

## 📦 Frappe Apps المخططة

```
opentra_admin      → على Admin Server (ERPNext الداخلي للشركة)
opentra_core       → على Customer Server (base لكل العملاء)
opentra_retention  → ميزة مدفوعة (أولوية عالية)
opentra_hr_premium
opentra_payroll_ksa
opentra_payroll_gcc
opentra_zatca_premium
opentra_reports
opentra_pos
opentra_manufacturing
opentra_warehouse
opentra_projects
```

---

## ✅ القرارات النهائية (لا تُعاد للنقاش)

### ZATCA
- **المختار:** `KSA Compliance` by LavaLoon (v0.60+)
- **السبب:** install نظيف، مطوّر موثوق، separation of concerns
- **المرفوض:** `zatca_integration` (4 patches يدوية، retention معيوب)
- **على Customer Server:** `zatca_integration` موجود حالياً، الخطة: migration لـ KSA Compliance

### Retention
- **القرار:** بناء `opentra_retention` من الصفر كـ Frappe app منفصل
- **السبب:** كلا التطبيقين (zatca_integration و KSA Compliance) لا يعالجان retention محاسبياً بشكل صحيح
- **الحالة:** لم يُبنَ بعد — هو أول أولوية بعد opentra_admin

### Lifecycle العميل (لا حذف نهائي)
```
Trial (14 يوم)
    ↓
Active
    ↓ (انتهاء اشتراك)
Grace Period (30 يوم) — يعمل بشكل طبيعي
    ↓
Disabled — لا يستطيع الدخول، البيانات محفوظة
    ↓ (بعد فترة طويلة أو طلب)
Archived — البيانات محفوظة، Site معطّل
```
**ملاحظة:** الحذف الكامل فقط بطلب صريح من العميل أو قرار إداري. العميل يستطيع الدفع وإعادة التفعيل في أي مرحلة حتى Archived.

### النموذج التجاري
- **Pricing:** ديناميكي بالكامل من Admin Panel
- **Pricing Models:** flat / per_user / per_transaction / tiered
- **Trial:** 14 يوم + extended 30 يوم عند الطلب
- **Grace Period:** 30 يوم (يعمل بشكل طبيعي)
- **Free Tier:** ❌ لا يوجد
- **Enterprise:** Custom Quote عبر فورم

### الأمان
- **Internal API (Admin ↔ Customer Server):** JWT signed + mTLS
- **Customer Auth:** OAuth2 (Admin Server = provider)

### Currencies
SAR + AED + KWD + QAR + BHD + OMR + JOD + USD (تسعير يدوي لكل عملة)

---

## 📊 DocTypes المخططة (opentra_admin)

### Pricing Engine
1. `Opentra Pricing Plan`
2. `Opentra Feature`
3. `Opentra Feature Dependency`
4. `Opentra User Pricing Tier`
5. `Opentra Storage Pricing`
6. `Opentra Discount Rule`
7. `Opentra Pricing Settings` (Single)
8. `Opentra Currency Pricing`

### Lifecycle
9. `Opentra Customer Site`
10. `Opentra Subscription`
11. `Opentra Lifecycle Log`
12. `Opentra Lifecycle Settings` (Single)

### Enterprise
13. `Opentra Lead`

---

## 🔴 الوضع الحالي

**آخر جلسة:** Opentra-02 (أبريل 2026)  
**آخر قرار:** Strategy A محسومة — KSA Compliance لـ ZATCA + opentra_retention منفصل  
**ما لم يُبنَ بعد:**
- [ ] `opentra_admin` Frappe app على Admin Server
- [ ] أي DocType من القائمة أعلاه
- [ ] `opentra_retention` module
- [ ] Next.js Public Site / Portal
- [ ] Demo Site

**الخطوة التالية:**
```bash
# على Admin Server (45.90.220.57)
cd /home/frappe/frappe-bench
bench new-app opentra_admin
bench --site erp.opentech.sa install-app opentra_admin
```
ثم إنشاء أول DocType: `Opentra Feature`

---

## 📁 ملفات السياق

| الملف | الوصف |
|---|---|
| `DECISIONS.md` | كل القرارات المعمارية مع المبررات |
| `ARCHITECTURE.md` | البنية التفصيلية والـ APIs |
| `app.py` | Provisioning API (Flask) |
| `install_hook.sh` | يُنفَّذ بعد إنشاء كل site |
| `setup_wizard_hook.py` | يضيف VAT + ZATCA تلقائياً |

---

## ⚙️ قواعد العمل مع Claude

1. **اقرأ هذا الملف أولاً** قبل أي عمل
2. **لا تُعِد نقاش القرارات المحسومة** إلا بطلب صريح
3. **الكود:** Python Frappe-idiomatic، تعليقات بالإنجليزي، التواصل بالعربي
4. **عند نهاية الجلسة:** حدّث قسم "الوضع الحالي" في هذا الملف
5. **DECISIONS.md هو المرجع** — أي تعارض → DECISIONS.md يتقدم
