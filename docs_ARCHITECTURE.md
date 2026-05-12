# Opentra SaaS — وثيقة المعمارية الرسمية

> **Version:** 2.0 — Approved
> **Last Updated:** May 2026
> **Status:** Production Ready

## 1. Vision

**Opentra** is a fully managed ERPNext SaaS platform for SMBs in Saudi Arabia and GCC, with built-in ZATCA (Phase 1 & 2) compliance and industry-specific customizations.

**Business Model:** Modular Subscriptions — customers pay only for features they need.

**ICP:** Saudi/GCC SMBs, 5–100 employees, needing full ERP + ZATCA, budget 500–5,000 SAR/month.

## 2. High-Level Architecture — 3 Systems + 3 Portals

```
INTERNET
   │
   ├── erp.opentech.sa (178.105.139.103)
   │   └── System 1: Admin Portal (ERPNext + opentra_admin)
   │
   ├── opentra.opentech.sa
   │   └── System 2: Customer Portal (Next.js)
   │       ├── Portal A: Public (Landing, Pricing, Signup)
   │       └── Portal B: Private (Dashboard, Billing, Backup)
   │
   └── *.opentra.opentech.sa (178.105.139.103)
       └── System 3: Customer Server (Frappe bench)
           ├── erp.opentech.sa (Admin/Production)
           ├── training.opentech.sa
           ├── demo.opentra.opentech.sa (planned)
           └── {client}.opentra.opentech.sa (per tenant)
```

## 3. Current Infrastructure

```
Server: Hetzner CX23 — 178.105.139.103
  OS    : Ubuntu 22.04.4 LTS
  CPU   : 2 vCPU
  RAM   : 4 GB
  Disk  : 40 GB NVMe
  Cost  : $5.59/month

Frappe bench (/home/frappe/frappe-bench):
  frappe              : 15.100.1
  erpnext             : 15.98.1
  hrms                : 15.58.1
  ksa_compliance      : lavaloon-eg (ZATCA Phase 1 & 2) ✅
  ksa_vat_reports     : custom
  erpnext_enhancement : custom (450-Learning)
  lending             : 0.0.1
  payments            : 0.0.1

Active Sites:
  https://erp.opentech.sa      → Admin Portal (Production) ✅
  https://training.opentech.sa → Training ✅

SSL    : Let's Encrypt (auto-renew every 90 days) ✅
Backup : Cloudflare R2, daily 2:00 AM UTC ✅
```

## 4. Approved Technical Decisions

| Decision | Choice | Cost | Upgrade Path |
|----------|--------|------|--------------|
| Payment Gateway | Moyasar | 0 fixed + 2.2% | + Tap for GCC |
| Authentication | JWT on Admin Server | $0 | Keycloak/Auth0 |
| Backup Storage | Cloudflare R2 | $0 (10GB free) | + B2 archive |
| Monitoring | Uptime Kuma + Netdata | $0 | Grafana Cloud |
| Support | Crisp → Chatwoot | $0 | Freshdesk |
| Domain | `*.opentra.opentech.sa` | $0 | Custom domain add-on |
| Admin Server | Hetzner CX23 | $5.59/mo | CX33 one-click |
| ZATCA | lavaloon ksa_compliance (AGPL free) | $0 | opentra_zatca (future) |

## 5. Feature Apps

| App | Status | Pricing Model |
|-----|--------|--------------|
| `opentra_retention` | ✅ v0.1.0 complete & tested | flat |
| `opentra_zatca_premium` | planned | per_transaction |
| `opentra_hr_premium` | planned | per_user |
| `opentra_payroll_ksa` | planned | per_user |
| `opentra_pos` | planned | flat |

## 6. Roadmap

### Phase 0 — Foundation ✅ Complete (May 2026)
- [x] Architecture document v2.0
- [x] Migration Hostinger OpenVZ → Hetzner CX23 KVM
- [x] SSL + ZATCA Phase 2 Production CSID
- [x] Automatic daily backup → Cloudflare R2
- [x] opentra_retention v0.1.0 complete

### Phase 1 — Admin Portal MVP (Month 1–2)
- [ ] opentra_admin Frappe App
- [ ] Clients Dashboard
- [ ] Provisioning Panel
- [ ] Backup/Restore Panel

### Phase 2 — Customer Portal Public (Month 2–3)
- [ ] Landing Page + Pricing Calculator
- [ ] Signup + Moyasar Payment
- [ ] Auto-provisioning on payment

### Phase 3 — Customer Portal Private (Month 3–4)
- [ ] JWT Auth
- [ ] Subscription Dashboard
- [ ] Self-service Backup/Restore

### Phase 4 — Automation (Month 4–6)
- [ ] Auto-renewal + Auto-suspension
- [ ] Revenue Analytics
- [ ] ZATCA invoicing for clients

## 7. Cost Analysis

```
Current Monthly:
  Hetzner CX23    : $5.59
  Cloudflare R2   : $0.00 (free tier)
  SSL             : $0.00
  ─────────────────────────
  Total           : $5.59/month

At Scale (100+ clients):
  Hetzner CX32    : $8.59
  Cloudflare R2   : ~$7.50
  Hetzner Backup  : $1.12
  ─────────────────────────
  Total           : ~$17/month
```

## 8. Architecture Principles

1. **Feature as a Package** — Each feature = independent Frappe App
2. **Abstraction Over Implementation** — All external dependencies behind interfaces
3. **Zero Vendor Lock-in at MVP** — No expensive fixed subscriptions early on
4. **Separation of Control & Data** — Admin Server = business logic, Customer Server = data
5. **Graceful Degradation** — Admin ↔ Customer failure doesn't stop client sites

*Last updated: May 2026*
