# Opentra Platform — Architecture

## Vision

Opentra is an ERPNext SaaS platform targeting Saudi Arabia and the GCC market. Each customer operates
on a dedicated ERPNext site (hard multi-tenancy), giving full data isolation while sharing a single
Frappe bench on managed infrastructure. Optional feature apps extend the base ERPNext installation
per subscription tier. **opentra_retention** is the first such feature app.

---

## Infrastructure

| Item | Value |
|------|-------|
| Server | Hetzner Cloud — Ubuntu |
| Frappe bench | `/home/frappe/frappe-bench` |
| Bench user | `frappe` |
| Test tenant site | `ksatest.opentra.opentech.sa` |
| Test tenant DB | `_accb778e7cc289a1` |

### Common shell commands

```bash
# Run any bench command against the test site
su - frappe -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa <command>"

# Run SQL directly
mysql -u root _accb778e7cc289a1 -e "SELECT ..."

# Migrate after code changes
su - frappe -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa migrate"

# Clear cache
su - frappe -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa clear-cache"

# Restart workers
su - frappe -c "cd /home/frappe/frappe-bench && bench restart"
```

---

## Multi-Tenancy Model

```
Frappe Bench (single server)
├── ksatest.opentra.opentech.sa      ← tenant A
├── customer2.opentra.opentech.sa    ← tenant B
└── ...
```

Each site has its own:
- MariaDB database (name format: `_<hash>`)
- ERPNext + Frappe installation
- Independently installed optional feature apps

The platform app stack per site:

```
frappe (core framework)
└── erpnext (ERP)
    └── opentra_retention (optional — per subscription)
    └── opentra_<next_feature> (future optional apps)
```

---

## Three Portals

### 1. Admin Portal (Internal)
Standard ERPNext desk UI used by Opentech staff and internal accountants.
- Full system user access
- Manages all DocTypes directly
- URL: `https://<site>/app`

### 2. Customer Portal
External-facing portal for customers (contractors, vendors) to view their own data.
- Authenticated via `Customer Portal User` + `Customer Portal Tenant` DocTypes
- Scoped automatically to the customer's own records
- Feature access gated by `enable_retention` flag on tenant
- API base: `https://<site>/api/method/opentra_retention.api.<endpoint>`

### 3. Tenant Portal *(planned)*
Management layer for Opentech to configure tenant subscriptions and feature flags.

---

## Portal Authentication Model

```
User (Frappe User)
  └── Customer Portal User     [DocType]
        ├── tenant → Customer Portal Tenant
        └── portal_role

Customer Portal Tenant         [DocType]
  ├── customer → Customer
  ├── company → Company
  ├── is_active (bool)
  └── enable_retention (bool)   ← feature gate
```

- **System Users**: unrestricted access, no customer scoping
- **Portal Users**: auto-scoped to their `Customer Portal Tenant.customer` on every API call
- **Guests**: rejected with 401

All API endpoints call `_get_portal_customer()` which returns `None` for system users (no restriction)
or a dict with `{customer, company, tenant, portal_role, enable_retention}` for portal users.

---

## opentra_retention App

### Purpose
Automates the Payment Retention workflow common in Saudi construction and government contracts:
a percentage of each invoice is withheld (retained) until project completion, then released
back to the customer for payment.

### Retention Lifecycle

```
Sales Invoice (submit)
    │
    ▼
Retention JV created automatically:
    DR  Retention Receivable Account  = retention_amount
    CR  Debtors / AR                  = retention_amount
    (net effect: invoice AR outstanding = grand_total - retention_amount)
    │
    ▼ (when customer is owed the retained amount)
Retention Release (submit)
    │
    ▼
Release JV created automatically:
    DR  Debtors / AR                  = release_amount   [ref → Sales Invoice]
    CR  Retention Receivable Account  = release_amount
    (net effect: invoice AR outstanding increases by release_amount)
    │
    ▼
Payment Entry (standard ERPNext)
    DR  Bank / Cash                   = paid_amount
    CR  Debtors / AR                  = paid_amount
    │
    ▼
Retention Release.status → "Paid"
```

Status flow: `Draft → Submitted → Paid`  (cancelled: `→ Cancelled`)

### Key Files

| File | Role |
|------|------|
| `opentra_retention/api.py` | All `@frappe.whitelist()` RPC endpoints (9 total) |
| `opentra_retention/hooks.py` | DocType event wiring + client JS registration |
| `opentra_retention/custom/sales_invoice.py` | validate, on_submit, on_cancel handlers |
| `opentra_retention/custom/payment_entry.py` | on_submit, on_cancel handlers |
| `opentra_retention/opentra_retention/doctype/retention_release/retention_release.py` | Core DocType: validation, balance computation, JV creation/cancellation, mark_paid logic |
| `opentra_retention/setup/install.py` | after_install / after_migrate: custom fields, account type, print format, workspace, roles |
| `opentra_retention/public/js/retention_release.js` | Client form logic: live balance display, "Create Payment Entry" and "Print" buttons |
| `opentra_retention/public/js/sales_invoice.js` | Client form enhancements for retention fields |
| `opentra_retention/opentra_retention/doctype/customer_portal_tenant/` | Tenant configuration DocType |
| `opentra_retention/opentra_retention/doctype/customer_portal_user/` | Portal user mapping DocType |

### DocType Events (hooks.py)

| DocType | Event | Handler |
|---------|-------|---------|
| Sales Invoice | validate | `custom.sales_invoice.validate` — auto-calculates retention amount |
| Sales Invoice | on_submit | `custom.sales_invoice.on_submit` — creates Retention JV |
| Sales Invoice | on_cancel | `custom.sales_invoice.on_cancel` — cancels Retention JV |
| Payment Entry | on_submit | `retention_release.on_payment_entry_submit` — marks releases Paid |
| Payment Entry | on_cancel | `retention_release.on_payment_entry_cancel` — reverts releases to Released |

### Custom Fields

**Company** (added by install.py):

| Field | Type | Purpose |
|-------|------|---------|
| `default_retention_account` | Link → Account | Retention Receivable account used in all JVs |

**Sales Invoice** (added by install.py):

| Field | Type | Purpose |
|-------|------|---------|
| `custom_retention_percentage` | Select (10%, 5%) | Auto-calculate mode |
| `custom_retention_amount` | Currency | Retention withheld (auto or manual) |
| `custom_net_after_retention` | Currency (read-only) | grand_total − retention_amount |
| `custom_retention_jv` | Link → Journal Entry (read-only) | Auto-created JV reference |

**User** (added by install.py):

| Field | Type | Purpose |
|-------|------|---------|
| `custom_customer` | Link → Customer | Portal customer linkage (legacy; primary link is via Customer Portal User) |

### Account Type Extension

`install.py` adds `"Receivable Retention"` as a new option to `Account.account_type` via a
Frappe Property Setter (non-destructive, survives upgrades).

### Print Format

`"Retention Invoice"` — Arabic/RTL Jinja print format for Retention Release documents.
Displays as a non-VAT invoice to send to customers before payment. Supports partial releases.

### Roles

| Role | Desk Access | Purpose |
|------|-------------|---------|
| Retention Portal User | No | Assigned to external portal users |

---

## Testing

```bash
# End-to-end retention lifecycle test
su - frappe -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa \
  execute opentra_retention.test_retention_full.execute"

# Payment flow test
su - frappe -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa \
  execute opentra_retention.test_retention_payment.execute"
```

## Code Quality

```bash
# Lint + format (Python)
ruff check .
ruff format .

# Lint (JavaScript)
npx eslint opentra_retention/public/js/

# All pre-commit hooks
pre-commit run --all-files
```

---

## Future Feature Apps

The same pattern (`opentra_<feature>`) will be used for future optional modules:
- VAT reporting
- ZATCA e-invoicing integration
- Contract management
- Customer portal dashboard

Each will be an independently installable Frappe app following the same portal auth model.
