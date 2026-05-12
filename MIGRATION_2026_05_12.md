# Migration Log — Hostinger → Hetzner CX23

> **Date:** May 12, 2026
> **Status:** ✅ Complete

## Summary

Successfully migrated `erp.opentech.sa` and `training.opentech.sa` from Hostinger OpenVZ Plan 2 to Hetzner CX23 KVM.

## Why Migrate

| Issue | Old (Hostinger OpenVZ) | New (Hetzner CX23) |
|-------|----------------------|-------------------|
| RAM | 2 GB (critically low) | 4 GB |
| Virtualization | OpenVZ (deprecated Mar 2026) | KVM |
| Docker support | ❌ | ✅ |
| NVMe storage | ❌ HDD | ✅ |
| Same provider as customer server | ❌ | ✅ Private network |
| Cost | Paid until May 2027 | $5.59/month |

## What Was Migrated

### Sites
- `erp.opentech.sa` — Production ERPNext (Admin Portal)
- `training.opentech.sa` — Training site

### Apps (8 total)
| App | Source |
|-----|--------|
| frappe 15.100.1 | GitHub (frappe/frappe) |
| erpnext 15.98.1 | GitHub (frappe/erpnext) |
| hrms 15.58.1 | GitHub (frappe/hrms) |
| payments 0.0.1 | GitHub (frappe/payments) |
| lending 0.0.1 | GitHub (frappe/lending) |
| ksa_compliance | GitHub (lavaloon-eg/ksa_compliance) |
| ksa_vat_reports | scp from old server (no remote) |
| erpnext_enhancement | scp from old server (private repo 450-Learning) |

### Data Sizes
- erp.opentech.sa DB: 8.9 MB, Files: 51 MB, Private: 730 KB
- training.opentech.sa DB: 2.3 MB, Files: 490 KB, Private: 140 KB

## Post-Migration Tasks Completed

- [x] SSL via certbot (Let's Encrypt) for both sites
- [x] ZATCA Phase 2 re-onboarding (new Production CSID)
- [x] LavaLoon premium announcement banner removed
- [x] Server scripts enabled (`server_script_enabled: true`)
- [x] Scheduler enabled for both sites
- [x] Developer mode disabled (production)
- [x] Automatic daily backup → Cloudflare R2 (cron 2:00 AM)
- [x] rclone configured for R2 uploads
- [x] Backup retention: 30 days

## Infrastructure Config

```
/home/frappe/frappe-bench/sites/erp.opentech.sa/site_config.json:
  host_name              : https://erp.opentech.sa
  server_script_enabled  : true
  developer_mode         : 0

Cron jobs (root):
  0 2 * * *  /home/frappe/backup-to-r2.sh
  @daily     certbot renew (auto-installed by certbot)

Cloudflare R2:
  Bucket  : opentech-backups
  Endpoint: https://d506c076138814094ffbbe5bd99e90a4.r2.cloudflarestorage.com
  Path    : opentech-backups/erp.opentech.sa/
```

## Issues Encountered & Resolved

| Issue | Resolution |
|-------|-----------|
| `bench install.py` 404 | Manual installation via pip + step-by-step |
| MariaDB root access denied | Used `sudo mariadb` socket auth |
| nginx log_format "main" unknown | Added log_format to nginx.conf via sed |
| Supervisor config not linked | `ln -sf config/supervisor.conf /etc/supervisor/conf.d/` |
| bench build RAM crash | Used tmux to keep session alive |
| assets 404 after build | Fixed with `chmod -R 755 /home/frappe` |
| Server scripts disabled | Added to both site_config and common_site_config |
| ZATCA compliance steps failed | Enabled server_script_enabled in common_site_config |
| LavaLoon banner in DB | Deleted from `tabCustom HTML Block` + cleared patch log |

## Pending

- [ ] Enable Hetzner Backup add-on ($1.12/month) — panel in maintenance during migration
- [ ] Move Cloudflare DNS to Proxied (after 1 week stability)
- [ ] Decommission Hostinger server (after 1 week verification)

## DNS Changes

| Domain | Old IP | New IP | Status |
|--------|--------|--------|--------|
| `erp.opentech.sa` | `45.90.220.57` (Hostinger) | `178.105.139.103` (Hetzner) | ✅ Updated |
| `training.opentech.sa` | `45.90.220.57` (Hostinger) | `178.105.139.103` (Hetzner) | ✅ Updated |

DNS managed via Cloudflare. Both records set to "DNS only" (grey cloud) during migration, to be switched to "Proxied" after 1 week stability verification.
