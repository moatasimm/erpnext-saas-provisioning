# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**Opentra** — ERPNext SaaS platform for Saudi Arabia & GCC market.
**GitHub:** https://github.com/moatasimm/erpnext-saas-provisioning (branch: develop)

---

## Servers

### Server 1 — Admin Portal (erp.opentech.sa)
| | |
|--|--|
| Provider | Hetzner CX23 (KVM) |
| IP | `178.105.139.103` |
| OS | Ubuntu 22.04.4 LTS |
| RAM | 4 GB |
| Disk | 40 GB NVMe |
| Cost | $5.59/month |
| bench path | `/home/frappe/frappe-bench` |
| Sites | `erp.opentech.sa`, `training.opentech.sa` |
| Previous IP | `45.90.220.57` (Hostinger — decommissioning) |

**DNS (Cloudflare):**
- `erp.opentech.sa` → `178.105.139.103` (DNS only, to be Proxied after stability)
- `training.opentech.sa` → `178.105.139.103`

**Apps installed:**
- frappe 15.100.1
- erpnext 15.98.1
- hrms 15.58.1
- ksa_compliance 0.61.2 (from `moatasimm/opentra-ksa-compliance`)
- ksa_vat_reports (custom, local)
- erpnext_enhancement (custom, 450-Learning)
- lending 0.0.1
- payments 0.0.1

---

### Server 2 — Customer/Opentra Server
| | |
|--|--|
| Provider | Hetzner (existing) |
| IP | `77.42.75.231` |
| bench path | `/home/frappe/frappe-bench` |
| Sites | `demo.opentra.opentech.sa`, `fresh.opentra.opentech.sa`, `test2.opentra.opentech.sa` |

**Apps installed:**
- frappe 15.103.1
- erpnext 15.102.0
- ksa_compliance 0.60.1 (from `moatasimm/opentra-ksa-compliance`)
- opentra_retention 0.0.1 ✅ (complete & tested)

**Removed today:**
- `zatca_integration` (Beveren-Software-Inc) — removed, replaced by ksa_compliance

---

## Key Decisions Made

### ZATCA Compliance App
- **Official repo:** `https://github.com/moatasimm/opentra-ksa-compliance` (private)
- Based on lavaloon-eg/ksa_compliance v0.61.2 (AGPL)
- **Modifications:** Premium announcement banners removed from JS + DB
- **Both servers:** upstream remote → moatasimm/opentra-ksa-compliance
- **Protection:** `ignore_app_updates: ksa_compliance` in common_site_config
- **Installation:** Local (no GitHub needed) — `bench --site {site} install-app ksa_compliance`

### Backup System
- **Storage:** Cloudflare R2 bucket `opentech-backups`
- **Endpoint:** `https://d506c076138814094ffbbe5bd99e90a4.r2.cloudflarestorage.com`
- **Script:** `/home/frappe/backup-to-r2.sh` on 178.105.139.103
- **Schedule:** Daily 2:00 AM UTC (cron)
- **Retention:** 30 days
- **Scope:** erp.opentech.sa only (training excluded)

### SSL
- Let's Encrypt via certbot (auto-renew daily via systemd timer)
- Both `erp.opentech.sa` and `training.opentech.sa` covered

### ZATCA Phase 2
- Production CSID re-issued after server migration
- Compliance checks: all 6 passed (Simplified + Standard)
- Server scripts enabled: `server_script_enabled: true`

---

## Common Commands

### On 178.105.139.103 (Admin Server)
```bash
# Check services
supervisorctl status

# Backup manually
bash /home/frappe/backup-to-r2.sh

# Clear cache
su - frappe -c "cd /home/frappe/frappe-bench && bench --site erp.opentech.sa clear-cache"

# New site (future)
su - frappe -c "cd /home/frappe/frappe-bench && bench new-site {site} --mariadb-root-password OpenTech@2026 --admin-password {pass} --no-mariadb-socket"
```

### On 77.42.75.231 (Opentra Server)
```bash
# Install apps on new site
bench --site {site} install-app erpnext
bench --site {site} install-app ksa_compliance      # local, no GitHub needed
bench --site {site} install-app opentra_retention   # local, no GitHub needed

# Update ksa_compliance (manual, from Opentra repo only)
cd /home/frappe/frappe-bench/apps/ksa_compliance
git pull upstream master
bench --site {site} migrate
```

---

## Architecture Summary

```
System 1: erp.opentech.sa (178.105.139.103)
  → Admin Portal: ERPNext Desk + opentra_admin (planned)
  → Manages: clients, subscriptions, billing, backups

System 2: opentra.opentech.sa (planned)
  → Customer Portal: Next.js
  → Portal A: Public (landing, pricing, signup)
  → Portal B: Private (dashboard, billing, self-service)

System 3: 77.42.75.231
  → Customer sites: {client}.opentra.opentech.sa
  → Apps: frappe + erpnext + ksa_compliance + opentra_*
  → Provisioning API: Flask :5000 (planned)
```

See `docs/ARCHITECTURE.md` for full details.

---

## Roadmap Status

- [x] Phase 0: Foundation (May 2026) ✅
  - [x] Server migration Hostinger → Hetzner
  - [x] SSL + ZATCA Phase 2
  - [x] Backup → Cloudflare R2
  - [x] opentra_retention v0.1.0 complete
  - [x] opentra-ksa-compliance private repo
- [ ] Phase 1: Admin Portal MVP
- [ ] Phase 2: Customer Portal Public
- [ ] Phase 3: Customer Portal Private
- [ ] Phase 4: Automation & Scale
