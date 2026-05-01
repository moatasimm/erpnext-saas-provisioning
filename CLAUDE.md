# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

### Platform-level docs (Opentra SaaS)
Lives at `/home/frappe/frappe-bench/opentra-docs/`:

| File | Contents |
|------|----------|
| [`opentra-docs/ARCHITECTURE.md`](/home/frappe/frappe-bench/opentra-docs/ARCHITECTURE.md) | Full platform architecture: infrastructure, multi-tenancy, portals, provisioning, lifecycle |
| [`opentra-docs/DECISIONS.md`](/home/frappe/frappe-bench/opentra-docs/DECISIONS.md) | 16 Architecture Decision Records with rationale and trade-offs |
| [`opentra-docs/CHANGELOG.md`](/home/frappe/frappe-bench/opentra-docs/CHANGELOG.md) | Session-by-session build history (Sessions 1–5, Apr 2026) |
| [`opentra-docs/features/retention.md`](/home/frappe/frappe-bench/opentra-docs/features/retention.md) | Retention feature: business context, accounting model, bugs fixed, known limits |
| [`opentra-docs/features/retention_requirements.md`](/home/frappe/frappe-bench/opentra-docs/features/retention_requirements.md) | Original client requirements brief (source of truth for intended behaviour) |

**Test scripts** (not part of app source — do not deploy):

| File | Contents |
|------|----------|
| [`opentra-docs/tests/test_retention_full.py`](/home/frappe/frappe-bench/opentra-docs/tests/test_retention_full.py) | Full end-to-end retention flow test |
| [`opentra-docs/tests/test_retention_payment.py`](/home/frappe/frappe-bench/opentra-docs/tests/test_retention_payment.py) | Payment Entry retention GL test |
| [`opentra-docs/tests/test_run.sh`](/home/frappe/frappe-bench/opentra-docs/tests/test_run.sh) | Shell wrapper to run tests via bench execute |

**Archive** (source session logs, SQL diagnostics, original scripts):

```
opentra-docs/archive/
├── source/        ← chat_2.md … chat_6.md, ANALYSIS_REPORT.md
├── scripts/       ← vat_setup_testclient_opentra_opentech_sa.py
├── retention_doc.pdf
└── *.sql / *.sh   ← workspace diagnostics, fetch scripts
```

### App-level docs (this app)
Lives in [`docs/`](docs/):

| File | Contents |
|------|----------|
| [`docs/api.md`](docs/api.md) | All 9 API endpoints — params, response shapes, error codes, curl examples |
| [`docs/API.md`](docs/API.md) | Extended API reference (alternate format) |
| [`docs/feature.md`](docs/feature.md) | Links to platform docs |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | App-level architecture detail |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | App versioned changelog |

## Overview

`opentra_retention` is a Frappe/ERPNext custom app that implements a payment retention workflow. It automates the creation of Journal Entries for retention deductions on Sales Invoices and manages the lifecycle of releasing retained amounts back to the customer.

## Commands

### Site & DB (test environment)

```bash
# All bench commands (run as frappe user — must cd first)
su - frappe -c "cd /home/frappe/frappe-bench && bench --site test2.opentra.opentech.sa <command>"

# Direct SQL (DB name from sites/test2.opentra.opentech.sa/site_config.json)
mysql -u root _test2_opentra_c1ca6d72 -e "SELECT ..."

# demo site
su - frappe -c "cd /home/frappe/frappe-bench && bench --site demo.opentra.opentech.sa <command>"
```

### Testing
```bash
su - frappe -c "cd /home/frappe/frappe-bench && bench --site test2.opentra.opentech.sa \
  execute opentra_retention.test_retention_full.execute"

su - frappe -c "cd /home/frappe/frappe-bench && bench --site test2.opentra.opentech.sa \
  execute opentra_retention.test_retention_payment.execute"
```

### Linting
```bash
# Python (ruff)
ruff check .
ruff format .

# JavaScript
npx eslint opentra_retention/public/js/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Installation / Deployment
```bash
bench get-app opentra_retention <repo-url>
bench --site <site> install-app opentra_retention
bench restart   # ← CRITICAL: hooks (on_submit etc.) are NOT active until workers restart

# Re-run post-install setup (custom fields, accounts, print format, workspaces)
bench --site <site> execute opentra_retention.setup.install.after_install

# Rebuild JS assets after JS changes
bench --site <site> build --app opentra_retention

# Clear cache after Python/config changes
bench --site <site> clear-cache
```

> **⚠️ `bench restart` is mandatory after every `bench install-app`.**
> Workers load `hooks.py` at startup. Skipping the restart means `on_submit`, `on_cancel`, and
> `validate` hooks silently don't fire — documents will be created in an inconsistent state
> (missing JVs, missing GL entries) with no error logged.

### Manual per-company setup (cannot be automated)

After installing, each company needs these two steps done **once** via the ERPNext UI:

1. **Create Chart of Accounts entries** (Accounting → Chart of Accounts):
   - `1311 - Retention Receivable` — account type: **Receivable Retention**
   - `1312 - Retention Released Receivable` — account type: **Receivable** (standard)

2. **Link accounts in Company settings** (Setup → Company → Accounts tab):
   - *Default Retention Receivable Account* → `1311 - Retention Receivable`
   - *Default Retention Released Account* → `1312 - Retention Released Receivable`

   Without these, submitting a Sales Invoice with retention will show a warning and skip the JV,
   and submitting a Retention Release will throw an error.

## Architecture

### Retention Lifecycle

The core business flow is:
1. **Sales Invoice submit** → `custom/sales_invoice.py:on_submit()` creates a **Retention JV** that DRs the retention receivable account and CRs the AR account, removing retention from the customer's outstanding balance.
2. **Retention Release submit** → `opentra_retention/doctype/retention_release/retention_release.py:on_submit()` creates a **Release JV** that reverses the original hold (DR AR, CR Retention Receivable), making the amount payable again.
3. **Payment Entry submit** → `custom/payment_entry.py` marks linked Retention Releases as "Paid" when the payment covers the released amount.

Status flow: `Draft → Submitted (Released) → Paid`

### Key Files

| File | Role |
|------|------|
| `opentra_retention/api.py` | All `@frappe.whitelist()` RPC endpoints for portal and internal use |
| `opentra_retention/custom/sales_invoice.py` | Hook handlers for Sales Invoice events |
| `opentra_retention/custom/payment_entry.py` | Hook handlers for Payment Entry events |
| `opentra_retention/dashboard/sales_invoice.py` | Adds Retention Release to Sales Invoice dashboard connections panel |
| `opentra_retention/opentra_retention/doctype/retention_release/retention_release.py` | Core Retention Release DocType: validation, balance computation, JV creation/cancellation |
| `opentra_retention/opentra_retention/report/retention_status_report/retention_status_report.py` | Script Report: GL-based retention status per invoice (held/released/paid/outstanding) |
| `opentra_retention/setup/install.py` | Post-install: creates custom fields, account type, print format, workspaces, portal role |
| `opentra_retention/public/js/retention_release.js` | Client-side form logic: live balance, "Create Payment Entry" and "Print" buttons |
| `opentra_retention/public/js/sales_invoice.js` | Retention % auto-calc, dashboard indicator, "Create/View" buttons on Sales Invoice |

### Frappe Hooks (`hooks.py`)

DocType events are registered here and route to handlers in `custom/`:
- `Sales Invoice` → `on_submit`, `on_cancel`, `validate`
- `Payment Entry` → `on_submit`, `on_cancel`
- `override_doctype_dashboards` → adds Retention Release panel to Sales Invoice dashboard
- `doctype_js` → loads public JS for Retention Release and Sales Invoice
- `report_permission_map` → grants Retention Status Report access to three roles
- `after_install` / `after_migrate` → runs `setup/install.py:after_install()`

### Portal Multi-tenancy

System users have unrestricted access. Portal users authenticate through `Customer Portal User` → `Customer Portal Tenant`, which carries `customer`, `company`, `enable_retention`, and `portal_role`. Every whitelisted API call that serves portal data calls `_get_portal_customer()` first, which raises if the user is inactive or lacks a valid tenant.

### Custom Fields (added by install.py)

Created automatically on install/migrate via `create_custom_fields()`:

| DocType | Fieldname | Purpose |
|---------|-----------|---------|
| Company | `default_retention_account` | 1311 account (Receivable Retention) |
| Company | `default_retention_released_account` | 1312 account (approved but unpaid) |
| Sales Invoice | `custom_retention_percentage` | Select: 10%, 5%, or empty (manual) |
| Sales Invoice | `custom_retention_amount` | Auto-calculated or manually entered |
| Sales Invoice | `custom_net_after_retention` | Grand Total − Retention (read-only) |
| Sales Invoice | `custom_retention_jv` | Link to auto-created Retention JV |
| Payment Entry | `custom_retention_release` | Link to Retention Release (read-only) |
| User | `custom_customer` | Customer link for portal API access |

## Python Style

- Line length: 110 (ruff enforced)
- Target: Python 3.10+
- Import sort style: as configured in `pyproject.toml` (ruff isort)
- Handler functions use the signature `def on_submit(doc, method)` (not class methods)
- API helpers use `_success(data)` / `_error(msg, code)` patterns from `api.py`
- Errors are logged with `frappe.log_error()` before raising or returning error responses

## JavaScript Style

- ESLint config at `.eslintrc` with Frappe globals (`frappe`, `cur_frm`, `Vue`, `erpnext`)
- Frappe form events use `frappe.ui.form.on('DocType', { event: function(frm) {} })`
- Prettier for formatting (see `.pre-commit-config.yaml`)
