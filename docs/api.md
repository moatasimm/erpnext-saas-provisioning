# opentra_retention — API Reference

> This is the canonical API reference for `opentra_retention`.
> For platform-level context see the main docs:
> [`/opentra-docs/features/retention.md`](/home/frappe/frappe-bench/opentra-docs/features/retention.md)

---

## Overview

**Base URL:**
```
https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.<endpoint>
```

**Authentication:**
```bash
# Token (API key + secret from User doctype)
Authorization: token <api_key>:<api_secret>

# Or Basic auth (base64 encoded)
Authorization: Basic <base64(api_key:api_secret)>
```

**Standard Response Envelope** (Frappe wraps everything in `"message"`):
```json
{
  "message": {
    "success": true,
    "data": { ... },
    "message": "OK",
    "error": null,
    "code": null
  }
}
```

**Error Response:**
```json
{
  "message": {
    "success": false,
    "data": null,
    "message": "Human-readable description",
    "error": "Human-readable description",
    "code": "ERROR_CODE"
  }
}
```

**Common Error Codes:**

| Code | HTTP | Meaning |
|------|------|---------|
| `UNAUTHORIZED` | 401 | Not logged in |
| `FEATURE_DISABLED` | 403 | `enable_retention` off for this tenant |
| `PERMISSION_DENIED` | 403 | Portal user accessing another customer's data |
| `MISSING_CUSTOMER` | 400 | Required `customer` param absent |
| `INVOICE_NOT_FOUND` | 404 | Sales Invoice does not exist |
| `INVOICE_NOT_SUBMITTED` | 400 | Invoice is Draft or Cancelled |
| `NO_RETENTION` | 400 | Invoice has no retention amount |
| `EXCEEDS_OUTSTANDING` | 400 | Release amount > outstanding retention |
| `ERROR` | 400 | Unexpected / generic error |

**Portal User Behaviour:**
Portal users' `customer` and `company` params are **overridden** from their tenant record.
System users pass params as-is. See `_get_portal_customer()` in `api.py`.

---

## 1. get_my_profile

Returns the current user's profile and portal configuration.

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_my_profile" \
  -H "Authorization: token <api_key>:<api_secret>"
```

**Response `data`:**
```json
{
  "user": "john@example.com",
  "full_name": "John Smith",
  "email": "john@example.com",
  "user_type": "Website User",
  "portal": {
    "tenant": "TENANT-001",
    "tenant_name": "Acme Corp",
    "portal_role": "Retention Portal User",
    "customer": "CUST-0001",
    "company": "Opentech SA",
    "features": { "retention": true }
  }
}
```
`portal` is `null` for system users with no portal record.

---

## 2. get_retention_outstanding

Submitted invoices with unreleased retention.
Outstanding = `retention_amount − sum(submitted Retention Releases)`.

**Params:** `company` (required), `customer` (optional, portal-overridden)

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_outstanding" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "KSA Test Company"}'
```

**Response `data`:**
```json
{
  "invoices": [
    {
      "sales_invoice": "ACC-SINV-2026-00008",
      "customer": "CUST-0001",
      "customer_name": "Acme Corp",
      "posting_date": "2026-01-15",
      "grand_total": 575000.0,
      "retention_amount": 50000.0,
      "total_released": 0.0,
      "retention_outstanding": 50000.0
    }
  ],
  "total": 1
}
```

---

## 3. get_retention_summary

Company-level aggregated retention statistics.

> No portal customer guard — accepts any `company` string. Internal/admin use.

**Params:** `company` (required)

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_summary" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "KSA Test Company"}'
```

**Response `data`:**
```json
{
  "total_invoices_with_retention": 1,
  "total_retention_amount": 50000.0,
  "total_retention_released": 0.0,
  "total_retention_outstanding": 50000.0,
  "retention_account": "Retention Receivable - KTC"
}
```
`retention_account` returns `"NOT CONFIGURED"` if `Company.default_retention_account` is unset.

---

## 4. get_invoice_retention_status

Full retention status for a single invoice, including all related Retention Releases.

**Params:** `sales_invoice` (required)

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_invoice_retention_status" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"sales_invoice": "ACC-SINV-2026-00008"}'
```

**Response `data`:**
```json
{
  "sales_invoice": "ACC-SINV-2026-00008",
  "customer": "CUST-0001",
  "retention_jv": "ACC-JV-2026-00001",
  "retention_amount": 50000.0,
  "total_released": 0.0,
  "retention_outstanding": 50000.0,
  "releases": [
    {
      "name": "RET-REL-2026-00001",
      "release_date": "2026-06-01",
      "release_amount": 25000.0,
      "status": "Paid",
      "release_jv": "ACC-JV-2026-00010"
    }
  ]
}
```

---

## 5. make_retention_payment_entry

Creates a **Draft** Payment Entry from a submitted Retention Release.
Left in Draft so the user can adjust for partial payments.

**Params:** `retention_release` (required)

**Preconditions:** Release must be submitted (`docstatus=1`) and status = `"Submitted"`.

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.make_retention_payment_entry" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"retention_release": "RET-REL-2026-00001"}'
```

**Response `data`:**
```json
{ "name": "ACC-PAY-2026-00020" }
```

---

## 6. get_customer_invoices

All submitted Sales Invoices for a customer, with retention metadata.

**Params:** `customer` (required, portal-overridden), `company` (optional)

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_customer_invoices" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"customer": "CUST-0001", "company": "KSA Test Company"}'
```

**Response `data`:**
```json
{
  "invoices": [
    {
      "name": "ACC-SINV-2026-00008",
      "customer": "CUST-0001",
      "customer_name": "Acme Corp",
      "posting_date": "2026-01-15",
      "due_date": "2026-02-15",
      "grand_total": 575000.0,
      "outstanding_amount": 525000.0,
      "status": "Unpaid",
      "custom_retention_amount": 50000.0,
      "custom_retention_percentage": "10%",
      "company": "KSA Test Company",
      "has_retention": true
    }
  ],
  "total": 1
}
```

---

## 7. get_customer_retention_releases

All Retention Releases for a customer (excludes cancelled).

**Params:** `customer` (required, portal-overridden), `company` (optional), `status` (optional: `Draft` / `Submitted` / `Paid` / `Cancelled`)

```bash
# All releases
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_customer_retention_releases" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"customer": "CUST-0001"}'

# Filter by status
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_customer_retention_releases" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"customer": "CUST-0001", "status": "Submitted"}'
```

**Response `data`:**
```json
{
  "releases": [
    {
      "name": "RET-REL-2026-00001",
      "customer": "CUST-0001",
      "company": "KSA Test Company",
      "sales_invoice": "ACC-SINV-2026-00008",
      "release_date": "2026-06-01",
      "release_amount": 50000.0,
      "remaining_after_release": 0.0,
      "status": "Paid",
      "release_jv": "ACC-JV-2026-00010",
      "creation": "2026-06-01 10:30:00"
    }
  ],
  "total": 1
}
```

---

## 8. create_retention_release

Creates **and submits** a Retention Release in a single call. The Release JV is created on submit,
making the amount immediately payable.

**Params:**
| Param | Required | Notes |
|-------|----------|-------|
| `sales_invoice` | Yes | Invoice name |
| `release_amount` | Yes | Must not exceed outstanding retention |
| `release_date` | No | ISO date, defaults to today |
| `notes` | No | Free text |

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.create_retention_release" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_invoice": "ACC-SINV-2026-00008",
    "release_amount": 25000,
    "release_date": "2026-06-15",
    "notes": "First partial release"
  }'
```

**Response `data`:**
```json
{
  "name": "RET-REL-2026-00002",
  "status": "Submitted",
  "release_amount": 25000.0,
  "sales_invoice": "ACC-SINV-2026-00008",
  "release_jv": "ACC-JV-2026-00015"
}
```

---

## 9. get_retention_dashboard

Single call for the portal home page: summary + outstanding invoices + recent releases.

**Params:** `company` (required), `customer` (optional, portal-overridden)

```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_dashboard" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "KSA Test Company"}'
```

**Response `data`:**
```json
{
  "summary": {
    "total_invoices_with_retention": 1,
    "total_retention_amount": 50000.0,
    "total_retention_released": 25000.0,
    "total_retention_outstanding": 25000.0,
    "retention_account": "Retention Receivable - KTC"
  },
  "outstanding_invoices": [ { "...": "see endpoint 2" } ],
  "recent_releases": [ { "...": "see endpoint 7, capped at 10" } ]
}
```

---

## Quick Reference

| # | Endpoint | Write? | Portal Guard |
|---|----------|--------|-------------|
| 1 | `get_my_profile` | No | Any user |
| 2 | `get_retention_outstanding` | No | Customer-scoped |
| 3 | `get_retention_summary` | No | None (open) |
| 4 | `get_invoice_retention_status` | No | Customer-scoped |
| 5 | `make_retention_payment_entry` | Yes (Draft PE) | Customer-scoped |
| 6 | `get_customer_invoices` | No | Customer-scoped |
| 7 | `get_customer_retention_releases` | No | Customer-scoped |
| 8 | `create_retention_release` | Yes (Submit) | Customer-scoped |
| 9 | `get_retention_dashboard` | No | Customer-scoped |
