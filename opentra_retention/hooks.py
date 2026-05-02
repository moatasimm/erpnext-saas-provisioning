app_name = "opentra_retention"
app_title = "Opentra Retention"
app_publisher = "Opentech"
app_description = "Retention Management for ERPNext"
app_email = "admin@opentech.sa"
app_license = "mit"

# Run after install and after migrate (to ensure custom fields + accounts exist)
after_install = "opentra_retention.setup.install.after_install"
after_migrate = "opentra_retention.setup.install.after_install"

# Bundle the Retention Status Report so it is created on install/migrate
fixtures = [
    {"doctype": "Report", "filters": [["name", "in", ["Retention Status Report"]]]},
]

# Client-side scripts per DocType
doctype_js = {
    "Retention Release": "public/js/retention_release.js",
    "Sales Invoice":     "public/js/sales_invoice.js",
}

# Adds Retention Release to the Sales Invoice dashboard connections panel
override_doctype_dashboards = {
    "Sales Invoice": "opentra_retention.dashboard.sales_invoice.get_data",
}

# Report role access
report_permission_map = {
    "Retention Status Report": ["Accounts Manager", "Accounts User", "Retention Portal User"],
}

doc_events = {
    "Sales Invoice": {
        "validate":  "opentra_retention.custom.sales_invoice.validate",
        "on_submit": "opentra_retention.custom.sales_invoice.on_submit",
        "on_cancel": "opentra_retention.custom.sales_invoice.on_cancel",
    },
    "Payment Entry": {
        "on_submit": "opentra_retention.custom.payment_entry.on_submit",
        "on_cancel": "opentra_retention.custom.payment_entry.on_cancel",
    },
    # Auto-create retention accounts (1311 + 1312) for every new company
    "Company": {
        "after_insert": "opentra_retention.setup.install.on_company_created",
    },
}
