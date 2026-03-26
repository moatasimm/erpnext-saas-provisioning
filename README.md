# ERPNext SaaS Auto-Provisioning API

Auto-provision ERPNext tenant sites with Saudi Arabia VAT/ZATCA defaults.

## Quick Deploy

```bash
# On server as root:
cd /tmp
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd YOUR_REPO
chmod +x deploy.sh
./deploy.sh
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/provision` | Create new tenant site |
| GET | `/api/site/status?job_id=xxx` | Check provisioning status |
| GET | `/api/sites` | List all sites |
| POST | `/api/site/delete` | Delete a tenant site |
| POST | `/api/site/run-vat-setup` | Run VAT setup after wizard |

## Usage

```bash
# Provision new site
curl -X POST http://localhost:5000/api/provision \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{"subdomain":"client1","admin_password":"Pass123"}'

# Check status
curl -H 'X-API-Key: YOUR_KEY' \
  'http://localhost:5000/api/site/status?job_id=JOB_ID'

# After client completes Setup Wizard, run VAT setup
curl -X POST http://localhost:5000/api/site/run-vat-setup \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{"subdomain":"client1"}'
```

## What it does

1. Creates new Frappe site (subdomain.opentra.opentech.sa)
2. Installs ERPNext + ZATCA
3. Configures Nginx + SSL
4. Sets Saudi defaults (country, currency SAR, Arabic)
5. After Setup Wizard: creates VAT accounts (15%, Zero, Exempt) and tax templates

## Service Management

```bash
systemctl status erpnext-provision
systemctl restart erpnext-provision
journalctl -u erpnext-provision -f
tail -f /home/frappe/frappe-bench/logs/provisioning/provisioning.log
```
