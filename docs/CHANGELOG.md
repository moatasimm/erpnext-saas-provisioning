# Changelog

All notable changes to `opentra_retention` are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [0.1.0] — 2026-04-25

### Added

**Core retention lifecycle**
- `custom/sales_invoice.py`: `validate` handler — auto-calculates `custom_retention_amount` from
  `custom_retention_percentage` (10% or 5% of net_total); computes `custom_net_after_retention`
- `custom/sales_invoice.py`: `on_submit` handler — creates Retention JV on invoice submit:
  `DR Retention Receivable / CR AR` reducing customer outstanding by retention amount
- `custom/sales_invoice.py`: `on_cancel` handler — cancels the companion Retention JV

**Retention Release DocType** (`opentra_retention/doctype/retention_release/`)
- Tracks partial and full releases of retained amounts per Sales Invoice
- `on_submit`: creates Release JV (`DR AR / CR Retention Receivable`) restoring invoice outstanding
- `on_cancel`: cancels the Release JV
- Balance fields computed on validate: `retention_amount`, `total_already_released`,
  `remaining_before_release`, `remaining_after_release`
- `mark_paid_if_applicable()` static method marks releases as Paid when covered by a Payment Entry
- `retention_release_list.js`: list view enhancements

**Payment Entry integration** (`custom/payment_entry.py`)
- `on_submit`: marks linked Retention Release(s) as `Paid` when payment covers released amount
- `on_cancel`: reverts `Paid` Retention Releases back to `Released` status

**API** (`api.py`) — 9 whitelisted endpoints
- `get_my_profile` — current user profile + portal info
- `get_retention_outstanding` — invoices with unreleased retention
- `get_retention_summary` — company-level aggregated stats
- `get_invoice_retention_status` — per-invoice retention detail + release history
- `make_retention_payment_entry` — create Draft Payment Entry from a Retention Release
- `get_customer_invoices` — all customer invoices with retention flags
- `get_customer_retention_releases` — all releases for a customer (filterable by status)
- `create_retention_release` — create and auto-submit a Retention Release via API
- `get_retention_dashboard` — aggregated portal home-page data (summary + outstanding + recent)

**Portal authentication** (`api.py: _get_portal_customer()`)
- `Customer Portal User` + `Customer Portal Tenant` DocTypes for external user scoping
- System users bypass portal restrictions; portal users are automatically scoped to their customer
- `enable_retention` feature gate on `Customer Portal Tenant`

**Setup / install** (`setup/install.py`)
- Custom field `Company.default_retention_account` (Link → Account)
- Custom fields on Sales Invoice: `custom_retention_percentage`, `custom_retention_amount`,
  `custom_net_after_retention`, `custom_retention_jv`
- Custom field `User.custom_customer` for portal customer linkage
- New Account type `"Receivable Retention"` via Property Setter (non-destructive)
- `"Retention Invoice"` Arabic/RTL print format for Retention Release
- `"Retention Portal User"` role (no desk access) for external portal users
- Retention Release shortcut added to ERPNext Selling workspace

**Client-side** (`public/js/`)
- `retention_release.js`: live balance calculation, "Create Payment Entry" button, "Print" button
- `sales_invoice.js`: retention section enhancements on the Sales Invoice form

**Tests**
- `test_retention_full.py`: end-to-end lifecycle (invoice → retention JV → release → payment)
- `test_retention_payment.py`: payment entry + mark_paid flow

**Translations**
- `translations/ar.csv`: Arabic translations for UI strings

**Tooling**
- `pyproject.toml`: ruff linting (line length 110, Python 3.10+)
- `.eslintrc`: ESLint config with Frappe globals
- `.pre-commit-config.yaml`: ruff, eslint, prettier, pyupgrade hooks
- `ensure_installed.sh`: pip dependency helper script

### Technical Notes
- Retention JV on invoice submit uses no `reference_type`/`reference_name` on the DR leg
  (Retention Receivable ≠ debit_to; ERPNext validates AR references must match `debit_to`)
- Release JV on Retention Release submit puts the `reference_type/reference_name` on the DR leg
  (AR account = debit_to), which restores the invoice's `outstanding_amount`
- `after_install` and `after_migrate` both call the same setup function (idempotent)
- Payment Entry creation (`make_retention_payment_entry`) leaves PE in Draft intentionally to allow
  partial payment adjustments before final submission
