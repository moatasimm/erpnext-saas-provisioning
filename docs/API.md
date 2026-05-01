# Opentra Retention — API Reference

## Overview

All endpoints are Frappe whitelisted methods exposed over HTTP.

**Base URL**
```
https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.<endpoint>
```

**Authentication**
All requests require a valid Frappe session or API key. Pass credentials via:
- Session cookie (browser / Postman with cookie jar)
- HTTP Basic Auth: `Authorization: Basic base64(api_key:api_secret)`
- Token Auth: `Authorization: token <api_key>:<api_secret>`

**Standard Response Envelope**
Every endpoint returns the same JSON structure:
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
On error:
```json
{
  "message": {
    "success": false,
    "data": null,
    "message": "Human-readable error",
    "error": "Human-readable error",
    "code": "ERROR_CODE"
  }
}
```
Frappe wraps the return value of whitelisted methods inside `"message"`.

**Common Error Codes**

| Code | HTTP | Meaning |
|------|------|---------|
| `UNAUTHORIZED` | 401 | Not logged in |
| `FEATURE_DISABLED` | 403 | `enable_retention` is off for this tenant |
| `PERMISSION_DENIED` | 403 | Portal user accessing another customer's data |
| `MISSING_*` | 400 | Required parameter not provided |
| `INVOICE_NOT_FOUND` | 404 | Sales Invoice does not exist |
| `INVOICE_NOT_SUBMITTED` | 400 | Invoice is Draft or Cancelled |
| `NO_RETENTION` | 400 | Invoice has no retention amount |
| `EXCEEDS_OUTSTANDING` | 400 | Release amount > outstanding retention |
| `ERROR` | 400 | Generic / unexpected error |

---

## Authorization Behaviour

| User type | Restriction |
|-----------|-------------|
| System User | None — all parameters accepted as-is |
| Portal User | `customer` and `company` are **overridden** from the tenant record; `enable_retention` gate is enforced |
| Guest | Rejected with 401 / `UNAUTHORIZED` |

---

## Endpoints

---

### 1. `get_my_profile`

Returns the current authenticated user's profile and portal configuration.

**Method:** GET or POST  
**Parameters:** none

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
    "features": {
      "retention": true
    }
  }
}
```
`portal` is `null` for system users with no portal record.

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_my_profile" \
  -H "Authorization: token <api_key>:<api_secret>"
```

---

### 2. `get_retention_outstanding`

Returns all submitted Sales Invoices that still have unreleased retention.

Outstanding retention = `retention_amount` − sum of submitted Retention Releases.

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `company` | string | Yes | Company name |
| `customer` | string | No | Filter by customer (ignored for portal users — overridden automatically) |

**Response `data`:**
```json
{
  "invoices": [
    {
      "sales_invoice": "ACC-SINV-2025-00001",
      "customer": "CUST-0001",
      "customer_name": "Acme Corp",
      "posting_date": "2025-01-15",
      "grand_total": 100000.0,
      "retention_amount": 10000.0,
      "total_released": 5000.0,
      "retention_outstanding": 5000.0
    }
  ],
  "total": 1
}
```

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_outstanding" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "Opentech SA"}'
```

---

### 3. `get_retention_summary`

Returns company-level aggregated retention statistics.

> **Note:** This endpoint does **not** enforce the portal customer guard. It accepts any `company`
> string. Suitable for internal/admin use.

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `company` | string | Yes | Company name |

**Response `data`:**
```json
{
  "total_invoices_with_retention": 12,
  "total_retention_amount": 500000.0,
  "total_retention_released": 120000.0,
  "total_retention_outstanding": 380000.0,
  "retention_account": "Retention Receivable - OS"
}
```
`retention_account` is `"NOT CONFIGURED"` if `Company.default_retention_account` is unset.

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_summary" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "Opentech SA"}'
```

---

### 4. `get_invoice_retention_status`

Returns full retention status for a single Sales Invoice, including all related Retention Releases.

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `sales_invoice` | string | Yes | Sales Invoice name (e.g. `ACC-SINV-2025-00001`) |

**Response `data`:**
```json
{
  "sales_invoice": "ACC-SINV-2025-00001",
  "customer": "CUST-0001",
  "retention_jv": "ACC-JV-2025-00042",
  "retention_amount": 10000.0,
  "total_released": 5000.0,
  "retention_outstanding": 5000.0,
  "releases": [
    {
      "name": "RET-REL-2025-00001",
      "release_date": "2025-06-01",
      "release_amount": 5000.0,
      "status": "Paid",
      "release_jv": "ACC-JV-2025-00099"
    }
  ]
}
```
`releases` excludes cancelled records (`docstatus != 2`).

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_invoice_retention_status" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"sales_invoice": "ACC-SINV-2025-00001"}'
```

---

### 5. `make_retention_payment_entry`

Creates a Payment Entry in **Draft** state from a submitted Retention Release.

The PE is pre-filled with `release_amount` and references the original Sales Invoice. Left in Draft
so the user can adjust the amount for partial payments before submitting.

Accounting after the Release JV has already restored AR:
```
DR  Bank / Cash         = release_amount
CR  Debtors / AR        = release_amount   [ref → Sales Invoice]
```

**Method:** POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `retention_release` | string | Yes | Retention Release name |

**Preconditions:**
- Retention Release must be submitted (`docstatus=1`)
- Retention Release status must be `"Submitted"` (not yet Paid)

**Response `data`:**
```json
{
  "name": "ACC-PAY-2025-00055"
}
```

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.make_retention_payment_entry" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"retention_release": "RET-REL-2025-00001"}'
```

---

### 6. `get_customer_invoices`

Returns all submitted Sales Invoices for a customer, including retention metadata.

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `customer` | string | Yes | Customer name (ignored for portal users — overridden) |
| `company` | string | No | Filter by company |

**Response `data`:**
```json
{
  "invoices": [
    {
      "name": "ACC-SINV-2025-00001",
      "customer": "CUST-0001",
      "customer_name": "Acme Corp",
      "posting_date": "2025-01-15",
      "due_date": "2025-02-15",
      "grand_total": 100000.0,
      "outstanding_amount": 90000.0,
      "status": "Unpaid",
      "custom_retention_amount": 10000.0,
      "custom_retention_percentage": "10%",
      "company": "Opentech SA",
      "has_retention": true
    }
  ],
  "total": 1
}
```

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_customer_invoices" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"customer": "CUST-0001", "company": "Opentech SA"}'
```

---

### 7. `get_customer_retention_releases`

Returns all Retention Releases for a customer (excludes cancelled).

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `customer` | string | Yes | Customer name (ignored for portal users — overridden) |
| `company` | string | No | Filter by company |
| `status` | string | No | One of: `Draft`, `Submitted`, `Paid`, `Cancelled` |

**Response `data`:**
```json
{
  "releases": [
    {
      "name": "RET-REL-2025-00001",
      "customer": "CUST-0001",
      "company": "Opentech SA",
      "sales_invoice": "ACC-SINV-2025-00001",
      "release_date": "2025-06-01",
      "release_amount": 5000.0,
      "remaining_after_release": 5000.0,
      "status": "Paid",
      "release_jv": "ACC-JV-2025-00099",
      "creation": "2025-06-01 10:30:00"
    }
  ],
  "total": 1
}
```

**curl example:**
```bash
# All releases for a customer
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

---

### 8. `create_retention_release`

Creates **and immediately submits** a Retention Release for a Sales Invoice.

This is a combined insert + submit in one API call. On submission, the Release JV is automatically
created (DR AR, CR Retention Receivable), making the amount payable immediately.

**Method:** POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `sales_invoice` | string | Yes | Sales Invoice name |
| `release_amount` | float | Yes | Amount to release (must not exceed outstanding retention) |
| `release_date` | string | No | ISO date `YYYY-MM-DD` — defaults to today |
| `notes` | string | No | Free-text notes |

**Validations:**
- Invoice must exist and be submitted
- Invoice must have `custom_retention_amount > 0`
- `release_amount` must not exceed `retention_outstanding`
- Portal users: invoice must belong to their customer

**Response `data`:**
```json
{
  "name": "RET-REL-2025-00003",
  "status": "Submitted",
  "release_amount": 5000.0,
  "sales_invoice": "ACC-SINV-2025-00001",
  "release_jv": "ACC-JV-2025-00105"
}
```

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.create_retention_release" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_invoice": "ACC-SINV-2025-00001",
    "release_amount": 5000,
    "release_date": "2025-06-15",
    "notes": "First partial release"
  }'
```

---

### 9. `get_retention_dashboard`

Single endpoint for the portal home page. Aggregates summary, outstanding invoices, and recent
releases in one call.

**Method:** GET or POST  
**Parameters:**

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `company` | string | Yes | Company name |
| `customer` | string | No | Customer filter (ignored for portal users — overridden) |

**Response `data`:**
```json
{
  "summary": {
    "total_invoices_with_retention": 12,
    "total_retention_amount": 500000.0,
    "total_retention_released": 120000.0,
    "total_retention_outstanding": 380000.0,
    "retention_account": "Retention Receivable - OS"
  },
  "outstanding_invoices": [
    {
      "sales_invoice": "ACC-SINV-2025-00001",
      "customer": "CUST-0001",
      "customer_name": "Acme Corp",
      "posting_date": "2025-01-15",
      "grand_total": 100000.0,
      "retention_amount": 10000.0,
      "total_released": 0.0,
      "retention_outstanding": 10000.0
    }
  ],
  "recent_releases": [
    {
      "name": "RET-REL-2025-00001",
      "customer": "CUST-0001",
      "sales_invoice": "ACC-SINV-2025-00001",
      "release_date": "2025-06-01",
      "release_amount": 5000.0,
      "status": "Paid"
    }
  ]
}
```
`recent_releases` is capped at 10 records, ordered by `release_date desc`.

**curl example:**
```bash
curl -X POST \
  "https://ksatest.opentra.opentech.sa/api/method/opentra_retention.api.get_retention_dashboard" \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"company": "Opentech SA"}'
```

---

## Quick Reference Table

| # | Endpoint | Method | Key Params | Auth Guard | Write? |
|---|----------|--------|-----------|------------|--------|
| 1 | `get_my_profile` | GET/POST | — | Any user | No |
| 2 | `get_retention_outstanding` | GET/POST | `company`, `customer?` | Portal scoped | No |
| 3 | `get_retention_summary` | GET/POST | `company` | None (open) | No |
| 4 | `get_invoice_retention_status` | GET/POST | `sales_invoice` | Portal scoped | No |
| 5 | `make_retention_payment_entry` | POST | `retention_release` | Portal scoped | Yes (Draft PE) |
| 6 | `get_customer_invoices` | GET/POST | `customer`, `company?` | Portal scoped | No |
| 7 | `get_customer_retention_releases` | GET/POST | `customer`, `company?`, `status?` | Portal scoped | No |
| 8 | `create_retention_release` | POST | `sales_invoice`, `release_amount`, `release_date?`, `notes?` | Portal scoped | Yes (Submit) |
| 9 | `get_retention_dashboard` | GET/POST | `company`, `customer?` | Portal scoped | No |
