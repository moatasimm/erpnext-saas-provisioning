# Session Log — 13 April 2026

> **Session focus:** KSA Compliance smoke test + Construction Retention evaluation  
> **Duration:** ~4 hours  
> **Outcome:** ✅ ZATCA strategy finalized, ❌ Retention requires custom build

---

## 📋 Executive Summary

| Question | Answer |
|---|---|
| Does `ksa_compliance` handle ZATCA correctly? | ✅ **YES** — 6/6 compliance checks Accepted |
| Does `ksa_compliance` handle Retention? | ❌ **NO** — ZATCA-only scope |
| Does ERPNext native handle Construction Retention? | ❌ **NO** — Payment Terms is soft split only |
| Final decision? | Adopt `ksa_compliance` + Build `opentra_retention` custom |

---

## 🏗️ Environment Details

### Servers
- **Customer Server:** `77.42.75.231` (Hetzner, Ubuntu 22.04)
  - User: `frappe`
  - Bench path: `/home/frappe/frappe-bench`
- **Admin Server:** `45.90.220.57` (`erp.opentech.sa`)

### Test Site
- **URL:** `https://ksatest.opentra.opentech.sa`
- **SSL:** Let's Encrypt (auto-renew via certbot)
- **Admin:** `Administrator` / `Admin_123`
- **MariaDB root:** `Admin_123`

### Installed Apps (final state)
```
frappe         15.103.1 version-15
erpnext        15.102.0 version-15
ksa_compliance 0.60.1   master
```

### Company
- **Name:** KSA Test Company
- **Abbr:** KTC
- **Country:** Saudi Arabia
- **Currency:** SAR
- **Tax ID (VAT):** 399999999900003 (sandbox)
- **Chart of Accounts:** Standard
- **⚠️ Known Issue:** `KSA Test Company (Demo)` (KTCD) exists but could not be deleted (tree accounts dependency). Mitigated via "Disabled" flag. **Future sites must handle this during provisioning.**

---

## 🔧 Phase 1: HTTPS Setup (SOLVED)

### Problem
After `bench drop-site` + `bench new-site`, nginx was serving the wrong certificate (`CN = provision.opentra.opentech.sa` instead of `ksatest`).

### Root Cause
nginx config lost the `server_name ksatest.opentra.opentech.sa` binding in HTTPS block after site recreation.

### Solution (tested, working)
```bash
# 1. Regenerate nginx config
sudo -iu frappe bash -c "cd /home/frappe/frappe-bench && bench setup nginx --yes"

# 2. Re-deploy existing certificate
sudo certbot --nginx \
  -d ksatest.opentra.opentech.sa \
  --non-interactive --agree-tos \
  -m admin@opentech.sa \
  --redirect --reinstall

# 3. Reload
sudo systemctl reload nginx

# 4. Verify
echo | openssl s_client -connect ksatest.opentra.opentech.sa:443 \
  -servername ksatest.opentra.opentech.sa 2>/dev/null | \
  openssl x509 -noout -subject
# Expected: subject=CN = ksatest.opentra.opentech.sa
```

### For Future Provisioning
Add to `opentra_core` provisioning script — **always run `bench setup nginx --yes` after `bench new-site`**, then `certbot --reinstall`.

---

## 🆕 Phase 2: Site Creation (CLEAN REBUILD)

### Full rebuild script (reference)
```bash
sudo -iu frappe bash <<'OUTER'
set -e
cd /home/frappe/frappe-bench

bench --site ksatest.opentra.opentech.sa backup --with-files

bench drop-site ksatest.opentra.opentech.sa \
    --db-root-username root \
    --db-root-password 'Admin_123' \
    --force \
    --no-backup

bench new-site ksatest.opentra.opentech.sa \
    --db-root-username root \
    --db-root-password 'Admin_123' \
    --admin-password 'Admin_123' \
    --install-app erpnext \
    --install-app ksa_compliance

bench --site ksatest.opentra.opentech.sa enable-scheduler
OUTER

# After rebuild, MUST reconfigure nginx+SSL (see Phase 1)
```

### Setup Wizard Values Used
| Field | Value |
|---|---|
| Language | English |
| Country | Saudi Arabia |
| Timezone | Asia/Riyadh |
| Currency | SAR |
| Company Name | KSA Test Company |
| Company Abbreviation | KTC |
| Chart of Accounts | Standard (⚠️ wizard did not offer "Standard with Numbers") |
| Fiscal Year | 2026-01-01 → 2026-12-31 |
| Setup Demo Data | No |

---

## 🛠️ Phase 3: VAT & Tax Infrastructure Setup

KSA Compliance does NOT auto-create VAT accounts. Ran custom setup script:

### `/tmp/setup_ktc.py` (executed successfully)
```python
import frappe
frappe.set_user("Administrator")

COMPANY = "KSA Test Company"
ABBR = "KTC"
DEMO = "KSA Test Company (Demo)"

# Set company tax_id
c = frappe.get_doc("Company", COMPANY)
c.tax_id = "399999999900003"
c.save(ignore_permissions=True)

# Find Duties and Taxes parent
parent = frappe.db.get_value("Account",
    {"company": COMPANY, "account_name": ["like", "%Duties and Taxes%"]}, "name")

# Create VAT Output + Input accounts
for label in ["Output", "Input"]:
    name = f"VAT 15% - {label} - {ABBR}"
    if not frappe.db.exists("Account", name):
        a = frappe.new_doc("Account")
        a.account_name = f"VAT 15% - {label}"
        a.company = COMPANY
        a.parent_account = parent
        a.account_type = "Tax"
        a.tax_rate = 15
        a.account_currency = "SAR"
        a.insert(ignore_permissions=True)

# Sales Tax Template with tax_category link (CRITICAL for ZATCA)
t = frappe.new_doc("Sales Taxes and Charges Template")
t.title = "KSA VAT 15%"
t.company = COMPANY
t.is_default = 1
t.tax_category = "Standard"  # MANDATORY for KSA Compliance
t.append("taxes", {
    "charge_type": "On Net Total",
    "account_head": f"VAT 15% - Output - {ABBR}",
    "description": "VAT 15%",
    "rate": 15
})
t.insert(ignore_permissions=True)

# Set default on company
c.default_sales_tax_template = "KSA VAT 15% - KTC"
c.save(ignore_permissions=True)

frappe.db.commit()
```

### Execution pattern (works consistently)
```bash
sudo tee /tmp/script.py > /dev/null <<'PYEOF'
# ... python code here ...
PYEOF

sudo chown frappe:frappe /tmp/script.py

sudo -iu frappe bash -c "cd /home/frappe/frappe-bench && bench --site ksatest.opentra.opentech.sa console" <<'STDIN'
exec(open('/tmp/script.py').read())
exit()
STDIN
```

---

## 🎯 Phase 4: ZATCA Onboarding (COMPLETE SUCCESS)

### UI Configuration (ZATCA Business Settings)

#### Tab 1: Seller Details
| Field | Value |
|---|---|
| Company | KSA Test Company |
| Company Unit | prim |
| Company Unit Serial | `1-Opentra\|2-ERPNext-15\|3-KTC-001` |
| Company Category | Other |
| Country | Saudi Arabia |
| Country Code | sa |
| Sync with ZATCA | Live |
| Type of Business Transactions | Let the system decide (both) |
| Currency | SAR |
| Street | King Fahad Road |
| Building Number | 1234 |
| City | Riyadh |
| Postal Code | 12211 |
| District | Al Olaya |

#### Tab 2: Seller ID
| Field | Value |
|---|---|
| Seller Name | KSA Test Company |
| VAT Registration Number | 399999999900003 |
| Additional IDs → CRN | 1010010000 |

#### Tab 3: VAT Account Configuration
- **Automatic VAT Account Configuration:** ❌ NOT USED (we pre-configured manually)

#### Tab 4: CLI
- **CLI Setup:** Automatic
- Clicked `Download and Set Up ZATCA CLI` → success (Java + ZATCA tool downloaded)

#### Tab 5: Integration
- **Validate Generated XML:** ✅ Enabled
- **Fatoora Server:** Sandbox

### Onboarding Sequence (all succeeded)
1. **Save** → Business Settings saved
2. **Click `Onboard`** → OTP prompt → entered `123345` → CSR generated + Compliance CSID received
3. **Click `Perform Compliance Checks`** → filled popup with test data:
   - Simplified Tax Customer: `Test B2C Customer`
   - Standard Tax Customer: `Test B2B Customer`
   - Item: `TEST-ITEM-01`
   - Tax Category: `Standard`
4. **Result:** 6/6 ACCEPTED
   ```
   ✅ Simplified Invoice      → Accepted
   ✅ Simplified Credit Note  → Accepted
   ✅ Simplified Debit Note   → Accepted
   ✅ Standard Invoice        → Accepted
   ✅ Standard Credit Note    → Accepted
   ✅ Standard Debit Note     → Accepted
   ```
5. **Click `Get Production CSID`** → success
6. **Tab Seller Details → Enable ZATCA Integration** ✅ → Save
7. **Created real Sales Invoice** → Submit → **ZATCA Status: Accepted** ✅

---

## ⚠️ KSA Compliance Gotchas (DISCOVERED)

These MUST be handled in `opentra_core` provisioning automation:

### Gotcha 1: Tax Category needs ZATCA category
**Error:** `Please set custom ZATCA category on Tax Category Standard`

**Solution:**
```python
tc = frappe.get_doc("Tax Category", "Standard")
tc.custom_zatca_category = "Standard rate"  # from Select options
tc.save(ignore_permissions=True)
```

**Select options discovered** (from `frappe.get_meta`):
- `Standard rate` (for 15% VAT)
- `Zero rated goods || Export of goods` (and 13 other variants)
- `Exempt from Tax || Financial services...` (and 4 other variants)
- `Services outside scope of tax / Not subject to VAT`

### Gotcha 2: Sales Tax Template needs `tax_category` link
**Error:** `Please set Tax Category on Sales Taxes and Charges Template KSA VAT 15% - KTC`

**Solution:** Set `tax_category` field when creating template (see Phase 3 script).

### Gotcha 3: Compliance check needs test customers + items
Popup asks for:
- Simplified Tax Customer (B2C, no tax_id)
- Standard Tax Customer (B2B, has tax_id + address)
- Item (with standard_rate)
- Tax Category

**Solution:** `/tmp/prep_compliance.py` — creates all test data. Referenced in `opentra_core` provisioning.

### Gotcha 4: Customer needs `tax_category` too
For ZATCA XML to validate, customer must have `tax_category = "Standard"` (or relevant).

### Gotcha 5: Demo company creation (by KSA Compliance post-install)
KSA Compliance post-install creates `<CompanyName> (Demo)` — a reference company with default Chart of Accounts. This can't be easily deleted (tree accounts). Options:
- Disable via `frappe.get_doc("Company", demo).disabled = 1`
- Ignore (doesn't affect main company)
- Delete during provisioning (needs bottom-up tree deletion)

---

## 🧪 Phase 5: Retention Investigation (NEGATIVE RESULT → CONFIRMED)

### Test Setup
```python
# Created via /tmp/setup_retention_test.py
# - Account: "Retention Receivable - KTC" (Current Asset, type=Receivable)
# - Payment Term: "Retention 5%" (365 credit days)
# - Payment Term: "Net 95% - 30 days"
# - Payment Terms Template: "Construction Progress Billing 5% Retention"
# - Project: PRJ-KTC-CONST-001 (for tracking)
```

### Test Scenario
```
Sales Invoice:
  Customer:          Test B2B Customer
  Project:           PRJ-KTC-CONST-001
  Item:              TEST-ITEM-01, Qty 1, Rate 50,000
  Tax Template:      KSA VAT 15% - KTC
  Payment Template:  Construction Progress Billing 5% Retention
  Total:             57,500 (50,000 + 7,500 VAT)
  Expected Behavior: 5% retention = 2,500 SAR held separately
```

### Actual Result (General Ledger)
```
Dr. Debtors - KTC          57,500.00    ← FULL AMOUNT in AR
    Cr. VAT 15% - Output        7,500.00
    Cr. Sales - KTC            50,000.00
```

### Critical Finding
**`Retention Receivable - KTC` account was NOT used.** ERPNext Payment Terms is a **soft split** affecting only Payment Schedule (due dates), NOT GL accounting.

### What's Required for Construction Retention
```
Dr. Debtors                    54,750  (95% of net + VAT: 47,500 + 7,125 VAT on 95%)
    OR (depending on VAT treatment)
Dr. Debtors                    55,000  (95% of net + full VAT: 47,500 + 7,500)
Dr. Retention Receivable        2,500  (5% of net, no VAT accrued yet)
    Cr. Sales                  50,000
    Cr. VAT Output              7,500
```

**VAT on retention is a business decision** — ZATCA allows both:
- **Option A:** Full VAT on invoice, retention is net-only (more common)
- **Option B:** VAT proportional to Debtors, VAT on retention deferred (less common, cleaner)

---

## 🏗️ opentra_retention — Design Specification

### Module Goal
Add Construction Retention support to Sales Invoice with proper GL accounting, fully compatible with `ksa_compliance` ZATCA integration.

### Repository
- **Name:** `opentra_retention`
- **Location:** `/home/frappe/frappe-bench/apps/opentra_retention/` (Customer Server)
- **Git:** To be created under `moatasimm/opentra_retention`

### DocTypes

#### 1. `Opentra Retention Settings` (Single)
Global retention configuration per company.

| Field | Type | Notes |
|---|---|---|
| `company` | Link (Company) | — |
| `default_retention_percent` | Percent | Default 5% |
| `default_retention_account` | Link (Account) | Filter: account_type=Receivable |
| `vat_treatment` | Select | "Full VAT on Invoice" / "Proportional VAT" (default: Full) |
| `auto_apply_for_construction` | Check | Auto-set retention when Project has "Construction" industry |
| `require_project_for_retention` | Check | Block retention if no Project linked |

#### 2. Custom Fields on `Sales Invoice`

| Field | Type | Insert After |
|---|---|---|
| `apply_retention` | Check | `is_return` |
| `retention_percent` | Percent | `apply_retention` — visible if apply_retention |
| `retention_amount` | Currency | `retention_percent` — read-only, auto-calculated |
| `retention_account` | Link (Account) | `retention_amount` — depends_on apply_retention |
| `retention_section_break` | Section Break | — |
| `net_payable_now` | Currency | `retention_account` — read-only, = grand_total - retention_amount |
| `retention_released_amount` | Currency | `net_payable_now` — for tracking releases |
| `retention_status` | Select | "Held" / "Partially Released" / "Fully Released" |

#### 3. `Opentra Retention Release`
Submittable document to release retention at project completion.

| Field | Type | Notes |
|---|---|---|
| `project` | Link (Project) | Mandatory |
| `customer` | Link (Customer) | Read-only from project |
| `release_date` | Date | Default today |
| `release_type` | Select | "Full Release" / "Partial Release" |
| `invoice_references` | Table (child) | Links to all Sales Invoices with retention on this project |
| `total_retention_held` | Currency | Sum from references |
| `amount_to_release` | Currency | User input |
| `remaining_after_release` | Currency | Calculated |
| `release_payment_entry` | Link (Payment Entry) | Created on submit |

**Child table `Opentra Retention Release Item`:**
- `sales_invoice` Link
- `invoice_date` Date (fetched)
- `original_retention` Currency (fetched)
- `previously_released` Currency (fetched)
- `current_release` Currency (user input)
- `remaining` Currency (calculated)

### GL Override Strategy

**Approach:** Hook into `Sales Invoice.make_gl_entries` via `doc_events`.

**File:** `opentra_retention/overrides/sales_invoice.py`

```python
import frappe
from frappe.utils import flt

def apply_retention_to_gl(doc, method):
    """
    Hook: doc_events -> Sales Invoice -> on_submit
    Modifies GL entries to split Debtors into Debtors + Retention Receivable
    """
    if not doc.get("apply_retention") or not doc.get("retention_amount"):
        return
    
    retention_amount = flt(doc.retention_amount)
    if retention_amount <= 0:
        return
    
    retention_account = doc.retention_account
    if not retention_account:
        frappe.throw(_("Retention Account is required when Apply Retention is enabled"))
    
    # Find existing Debtors GL entry for this invoice
    debtors_gle = frappe.db.sql("""
        SELECT name, debit, credit, account
        FROM `tabGL Entry`
        WHERE voucher_type = 'Sales Invoice'
        AND voucher_no = %s
        AND account = %s
    """, (doc.name, doc.debit_to), as_dict=True)
    
    if not debtors_gle:
        return
    
    # Reduce Debtors by retention amount
    original_debtors = debtors_gle[0]
    new_debtors_amount = flt(original_debtors.debit) - retention_amount
    
    frappe.db.set_value("GL Entry", original_debtors.name, {
        "debit": new_debtors_amount,
        "debit_in_account_currency": new_debtors_amount
    })
    
    # Add new GL entry for Retention Receivable
    gle = frappe.new_doc("GL Entry")
    gle.update({
        "posting_date": doc.posting_date,
        "account": retention_account,
        "party_type": "Customer",
        "party": doc.customer,
        "debit": retention_amount,
        "debit_in_account_currency": retention_amount,
        "credit": 0,
        "credit_in_account_currency": 0,
        "account_currency": doc.currency,
        "against_voucher_type": "Sales Invoice",
        "against_voucher": doc.name,
        "voucher_type": "Sales Invoice",
        "voucher_no": doc.name,
        "voucher_subtype": "Retention",
        "company": doc.company,
        "remarks": f"Retention {doc.retention_percent}% held from invoice {doc.name}"
    })
    gle.insert(ignore_permissions=True)
    
    # Update outstanding_amount
    doc.db_set("outstanding_amount", new_debtors_amount, update_modified=False)
    
    # Set retention status
    doc.db_set("retention_status", "Held", update_modified=False)
```

### hooks.py
```python
app_name = "opentra_retention"
app_title = "Opentra Retention"
app_publisher = "Opentra"
app_description = "Construction Retention for ERPNext"
app_version = "0.1.0"

doc_events = {
    "Sales Invoice": {
        "validate": "opentra_retention.overrides.sales_invoice.calculate_retention",
        "on_submit": "opentra_retention.overrides.sales_invoice.apply_retention_to_gl",
        "on_cancel": "opentra_retention.overrides.sales_invoice.reverse_retention_gl",
    }
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Opentra Retention"]]}
]
```

### Test Plan (Sprint 5 — Session 2)

#### Test Case 1: Basic Retention
```
Input:
  Customer: Test B2B Customer
  Item: 100,000 SAR
  Tax: KSA VAT 15%
  Retention: 5%
  Retention Account: Retention Receivable - KTC

Expected GL:
  Dr. Debtors                109,250  (95,000 net + 15,000 VAT - adjusted)
    Actually: 115,000 - 5,000 = 110,000
  Dr. Retention Receivable     5,000
    Cr. Sales                    100,000
    Cr. VAT Output                15,000

Expected Invoice Fields:
  grand_total:         115,000
  outstanding_amount:  110,000  ← excludes retention
  net_payable_now:     110,000
  retention_amount:      5,000
  retention_status:    "Held"
```

#### Test Case 2: ZATCA Compatibility
After retention applied:
- Sales Invoice Additional Fields (ZATCA XML) generated successfully
- ZATCA Status: Accepted
- QR code valid
- XML shows correct grand total (retention is accounting-only, not ZATCA XML concern)

#### Test Case 3: Partial Release
```
3 invoices with 5,000 retention each = 15,000 held
Release 10,000 → remaining 5,000
GL:
  Dr. Cash/Bank              10,000
    Cr. Retention Receivable   10,000
```

#### Test Case 4: Cancellation
Cancel invoice with retention → reverse retention GL entries
→ Retention Receivable balance restored

#### Test Case 5: Credit Note against retention invoice
Edge case — verify retention handling on returns

### Implementation Order (Session 2)

**Step 1** — Create app structure (15 min)
```bash
cd /home/frappe/frappe-bench
bench new-app opentra_retention
bench --site ksatest.opentra.opentech.sa install-app opentra_retention
```

**Step 2** — Create `Opentra Retention Settings` DocType (15 min)
- Single DocType with fields above
- Default values

**Step 3** — Custom Fields on Sales Invoice (20 min)
- Use fixtures or migration script
- Test visibility logic (depends_on)

**Step 4** — Validation hook (30 min)
- `calculate_retention()` — auto-fill retention_amount from percent
- Validation: retention_account is_frozen, company match, etc.

**Step 5** — GL override hook (45 min)
- `apply_retention_to_gl()` — the core logic above
- Test: submit invoice → verify GL

**Step 6** — ZATCA regression test (15 min)
- Submit invoice with retention
- Verify ZATCA Status: Accepted
- Verify XML validity

**Step 7** — Retention Release DocType (60 min)
- Full CRUD + Payment Entry generation

**Step 8** — Cancellation reversal (30 min)
- `reverse_retention_gl()` hook

**Step 9** — Documentation + push to GitHub (30 min)

**Total estimate:** ~4 hours

---

## 📂 Files Created During This Session

Stored in `/tmp/` on Customer Server. Save to repo:

| File | Purpose | Status |
|---|---|---|
| `/tmp/setup_ktc.py` | Initial company + VAT + tax template setup | ✅ Used |
| `/tmp/prep_compliance.py` | Creates test customers + item + tax category | ✅ Used |
| `/tmp/fix_tax_cat.py` | Adds tax_category link to Sales Tax Template | ✅ Used |
| `/tmp/fix_zatca_cat.py` | Sets custom_zatca_category on Tax Category | ✅ Used |
| `/tmp/link_tax.py` | Links default tax template to company | ✅ Used |
| `/tmp/setup_retention_test.py` | Payment Terms + Project setup for retention test | ✅ Used |
| `/tmp/kill_demo.py` | Attempts to delete KSA Test Company (Demo) | ⚠️ Partial |

**Action:** Move all working scripts to `scripts/ksa_compliance_provisioning/` in the repo for future reference.

---

## 🎯 Next Session Checklist

### Before starting
- [ ] Read `DECISIONS.md` v0.4
- [ ] Read `SESSION_LOG_2026-04-13.md` (this file)
- [ ] Confirm `ksatest.opentra.opentech.sa` still accessible
- [ ] Verify `bench --site ksatest... list-apps` shows 3 apps

### Session goals
- [ ] Create `opentra_retention` app skeleton
- [ ] Implement `Opentra Retention Settings` Single DocType
- [ ] Add Custom Fields to Sales Invoice
- [ ] Implement GL override (core logic)
- [ ] Pass Test Case 1 (Basic Retention)
- [ ] Pass Test Case 2 (ZATCA compatibility — critical!)
- [ ] Initial commit to GitHub

### Stretch goals
- [ ] Retention Release DocType
- [ ] Cancellation reversal
- [ ] Test Case 3-5

---

## 🔐 Credentials (for next session, keep secure)

| Resource | Value |
|---|---|
| Customer Server SSH | `root@77.42.75.231` |
| MariaDB root | `Admin_123` |
| Site Administrator | `Admin_123` |
| ZATCA Sandbox OTP | `123345` (reusable for sandbox) |
| Test VAT Number | `399999999900003` |
| Test B2B Customer VAT | `300000000000003` |

---

## 🌟 Wins from This Session

1. ✅ **ZATCA strategy settled** — no more ambiguity between zatca_integration vs ksa_compliance
2. ✅ **Production-ready ZATCA** on ksatest site (Production CSID obtained, real invoice Accepted)
3. ✅ **Retention problem clearly diagnosed** — no more guessing if ERPNext native works
4. ✅ **Complete design spec** for `opentra_retention` ready to build
5. ✅ **5 gotchas documented** for future provisioning automation
6. ✅ **Reusable scripts** produced (all in `/tmp/`, to be archived)

---

## 📝 Notes & Observations

- **LavaLoon's KSA Compliance is professional-grade.** Install was clean, onboarding automated, error messages helpful. Recommend as baseline.
- **ERPNext Payment Terms is documentation-misleading.** Many blog posts suggest it handles retention — it doesn't, at the GL level.
- **ZATCA sandbox is stable.** All 6 compliance checks passed on first attempt (after tax_category fix).
- **`bench console` via heredoc has limits.** Multi-line nested heredocs (`<<'OUTER'` with inner `<<'EOF'`) fail silently. Pattern that works: write file first, then `exec(open(...).read())`.
- **Tree account deletion is tricky.** `Company` with full CoA can't be deleted easily. Provisioning should handle this during setup, not after.

---

**End of Session Log — 2026-04-13**
