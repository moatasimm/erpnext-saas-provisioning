"""
One-shot script: cancel and re-submit Retention Releases on test2
so their Release JVs have no reference on the DR leg (Sales Invoice
outstanding is unaffected).

Handles mixed state: some releases may already be in Draft after a
partial run.

Run via:
  bench --site test2.opentra.opentech.sa execute opentra_retention.fix_release_jv_refs.execute
"""

import frappe


def execute():
    releases = frappe.get_all(
        "Retention Release",
        filters=[["docstatus", "in", [0, 1]]],
        fields=["name", "sales_invoice", "release_jv", "status", "docstatus"],
    )

    if not releases:
        print("No Retention Releases found.")
        return

    print(f"Found {len(releases)} Retention Release(s):")
    for r in releases:
        print(f"  {r.name}  docstatus={r.docstatus}  status={r.status}  jv={r.release_jv or '(none)'}")

    for r in releases:
        print(f"\n── Processing {r.name} ──")
        doc = frappe.get_doc("Retention Release", r.name)

        if doc.docstatus == 1:
            # Still submitted — cancel first (on_cancel also cancels the linked JV)
            print(f"  Cancelling {r.name} (JV {doc.release_jv})...")
            doc.cancel()
            frappe.db.commit()
            print(f"  ✓ Cancelled — JV reversed")
            doc.reload()

        if doc.docstatus == 2:
            # Cancelled — create amendment (fresh Draft)
            print(f"  Amending {r.name}...")
            amended = frappe.copy_doc(doc)
            amended.docstatus = 0
            amended.status = "Draft"
            amended.release_jv = ""
            amended.amended_from = doc.name
            amended.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  ✓ Amendment created: {amended.name}")
            doc = amended
        elif doc.docstatus == 0:
            # Already Draft from a partial previous run — just clear stale JV ref
            doc.db_set("release_jv", "")
            doc.db_set("status", "Draft")
            frappe.db.commit()
            doc.reload()
            print(f"  Already Draft — cleared stale release_jv")

        # Submit — on_submit creates a new JV with corrected (no) reference on DR leg
        print(f"  Submitting {doc.name}...")
        doc.submit()
        frappe.db.commit()
        doc.reload()
        print(f"  ✓ Submitted — new JV: {doc.release_jv}")

    print("\n── Verification ──")
    invoice_names = list({r.sales_invoice for r in releases})
    rows = frappe.db.sql(
        "SELECT name, grand_total, outstanding_amount, status FROM `tabSales Invoice` WHERE name IN ({})".format(
            ", ".join(["%s"] * len(invoice_names))
        ),
        invoice_names,
        as_dict=True,
    )
    for row in rows:
        print(
            f"  {row.name}: grand_total={row.grand_total}  outstanding={row.outstanding_amount}  status={row.status}"
        )

    print("\nDone.")
