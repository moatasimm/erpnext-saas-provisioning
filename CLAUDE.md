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

### Per-company setup (automated)

`after_install` (and `after_migrate`) now auto-creates the retention accounts for all existing
companies and wires them into Company settings. New companies get the same treatment via the
`Company.after_insert` hook.

**What `create_retention_accounts()` does per company:**
1. Finds the Accounts Receivable parent group (parent of the Debtors account)
2. Creates `1311 - Retention Receivable` (account type: Receivable Retention) — skips if exists
3. Creates `1312 - Retention Released Receivable` (account type: Receivable) — skips if exists
4. Sets both as defaults in Company → Retention Settings — skips if already set

**Nothing needs to be done manually.** If the accounts already exist (manually created before this
version), install.py detects them and skips creation but still wires the defaults if unset.

> **Fallback (edge case):** If install runs before the company's Chart of Accounts exists (e.g.
> on a brand-new ERPNext installation where Company is created before `bench install-app`),
> `create_retention_accounts()` will print a warning and skip. Run `after_install` again after
> the CoA is set up:
> ```bash
> bench --site <site> execute opentra_retention.setup.install.after_install
> ```

## Architecture

### Retention Lifecycle

Four GL events across two intermediate accounts (1311 and 1312):

1. **Sales Invoice submit** → `custom/sales_invoice.py:on_submit()` creates a **Retention JV**:
   `DR 1311 Retention Receivable | CR AR (Debtors)` — withholds retention from AR outstanding.
2. **Retention Release submit** → `retention_release.py:on_submit()` creates a **Release JV**:
   `DR 1312 Retention Released | CR 1311` — moves the amount to "approved for payment."
3. **Create Payment Entry** → `api.make_retention_payment_entry()` auto-creates a **Transfer JV**:
   `DR AR [ref: SI] | CR 1312` — restores SI outstanding so the PE can reference it.
   Then creates a Draft Payment Entry (`paid_from = AR`, `paid_to = Bank`).
4. **Payment Entry submit** → `custom/payment_entry.py:on_submit()` marks the Retention Release
   as "Paid". If PE is cancelled, Transfer JV is also cancelled and status reverts to "Submitted."

Status flow: `Draft → Submitted → Paid`  (cancellation branch: `→ Cancelled`)

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

| Hook | Value | Effect |
|------|-------|--------|
| `after_install` / `after_migrate` | `setup/install.py:after_install` | Creates fields, account type, accounts, print format, workspaces, role |
| `fixtures` | `Report: Retention Status Report` | Bundles report so it is created on install |
| `doctype_js` | Retention Release, Sales Invoice | Loads public JS for both DocTypes |
| `override_doctype_dashboards` | `dashboard/sales_invoice.py:get_data` | Adds Retention Release panel to SI connections panel |
| `report_permission_map` | Retention Status Report | Grants report access to 3 roles |
| `doc_events → Sales Invoice` | `validate`, `on_submit`, `on_cancel` | Auto-calc retention; create/cancel Retention JV |
| `doc_events → Payment Entry` | `on_submit`, `on_cancel` | Mark/revert Retention Release as Paid |
| `doc_events → Company` | `after_insert` | Auto-creates 1311 + 1312 accounts for every new company |

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
