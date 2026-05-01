"""
Migration: switch existing Retention Releases from JV-based to Retention Invoice-based.

Finds submitted Retention Releases whose release_jv points to a Journal Entry
(the old approach), cancels them (which cancels the JV), then re-submits them
so the new _create_retention_invoice() logic runs and creates proper Sales Invoices.

Run via:
  bench --site test2.opentra.opentech.sa execute \
    opentra_retention.migrate_to_retention_invoices.execute
"""

import frappe


def execute():
    # Find releases where release_jv is a Journal Entry (old approach)
    releases = frappe.get_all(
        "Retention Release",
        filters=[["docstatus", "=", 1]],
        fields=["name", "release_jv", "status", "sales_invoice", "customer"],
    )

    to_migrate = []
    for r in releases:
        if r.release_jv and frappe.db.exists("Journal Entry", r.release_jv):
            to_migrate.append(r)

    if not to_migrate:
        print("No Retention Releases with legacy JVs found — nothing to migrate.")
        return

    print(f"Found {len(to_migrate)} release(s) to migrate:")
    for r in to_migrate:
        print(f"  {r.name}  status={r.status}  jv={r.release_jv}  invoice={r.sales_invoice}")

    for r in to_migrate:
        print(f"\n── Migrating {r.name} ──")
        doc = frappe.get_doc("Retention Release", r.name)

        print(f"  Cancelling {r.name} (JV {doc.release_jv})...")
        doc.cancel()
        frappe.db.commit()
        print(f"  ✓ Cancelled")
        doc.reload()

        # Create amendment (fresh Draft)
        print(f"  Amending {r.name}...")
        amended = frappe.copy_doc(doc)
        amended.docstatus = 0
        amended.status = "Draft"
        amended.release_jv = ""
        amended.amended_from = doc.name
        amended.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"  ✓ Amendment created: {amended.name}")

        print(f"  Submitting {amended.name}...")
        amended.submit()
        frappe.db.commit()
        amended.reload()
        print(f"  ✓ Submitted — Retention Invoice: {amended.release_jv}")

    print("\n── Verification ──")
    for r in to_migrate:
        # Find the amendment that replaced this release
        amendment = frappe.db.get_value(
            "Retention Release",
            {"amended_from": r.name, "docstatus": 1},
            ["name", "release_jv", "status"],
            as_dict=True,
        )
        if amendment:
            si_status = frappe.db.get_value("Sales Invoice", amendment.release_jv, "status") if amendment.release_jv else "N/A"
            print(f"  {amendment.name}: status={amendment.status}  invoice={amendment.release_jv}  si_status={si_status}")
        else:
            print(f"  WARNING: no submitted amendment found for {r.name}")

    print("\nDone.")
