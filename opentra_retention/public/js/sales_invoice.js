// Sales Invoice — Retention Integration
// Adds "Retention Invoice" to the Create dropdown and shows balance indicator.

// ── Helper: calculate & set read_only when % changes or net_total/grand_total changes ──
function retention_handle_percentage(frm) {
    var pct = flt(frm.doc.custom_retention_percentage);
    if (pct > 0) {
        // Calculate from net_total (excluding VAT)
        var amount = flt(frm.doc.net_total) * pct / 100;
        frm.set_value('custom_retention_amount', Math.round(amount * 100) / 100);
        // Make read-only
        frm.set_df_property('custom_retention_amount', 'read_only', 1);
    } else {
        // Empty % — make editable
        frm.set_df_property('custom_retention_amount', 'read_only', 0);
    }
    frm.refresh_field('custom_retention_amount');
}

// ── Helper: set correct read_only state without recalculating ──
function retention_set_field_state(frm) {
    var pct = flt(frm.doc.custom_retention_percentage);
    if (pct > 0) {
        frm.set_df_property('custom_retention_amount', 'read_only', 1);
    } else {
        frm.set_df_property('custom_retention_amount', 'read_only', 0);
    }
    frm.refresh_field('custom_retention_amount');
}

frappe.ui.form.on('Sales Invoice', {

    // When Retention % changes
    custom_retention_percentage: function(frm) {
        retention_handle_percentage(frm);
    },

    // When net_total changes (recalculate if % is set)
    net_total: function(frm) {
        retention_handle_percentage(frm);
    },

    // When grand_total changes (recalculate if % is set)
    grand_total: function(frm) {
        retention_handle_percentage(frm);
    },

    // On form load
    onload: function(frm) {
        retention_set_field_state(frm);
    },

    refresh: function (frm) {

        // Set correct field state on refresh
        retention_set_field_state(frm);

        // ── 0. "View → Retention Release" — always visible on submitted invoices ──
        // (must be added BEFORE the early-return so it shows even when
        //  custom_retention_amount is zero or the invoice has no retention yet.)
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Retention Release'), function () {
                frappe.set_route('List', 'Retention Release', {
                    'sales_invoice': frm.doc.name
                });
            }, __('View'));

            frm.add_custom_button(__('Retention Report'), function () {
                frappe.set_route('query-report', 'Retention Status Report', {
                    company: frm.doc.company,
                    customer: frm.doc.customer,
                });
            }, __('View'));
        }

        var retention_amount = flt(frm.doc.custom_retention_amount);

        // The rest (indicator + Create button) only apply when retention exists
        if (frm.doc.docstatus !== 1 || retention_amount <= 0) return;

        // ── 1. Dashboard indicator (async) ────────────────────────────────
        frappe.call({
            method: 'opentra_retention.api.get_invoice_retention_status',
            args: { sales_invoice: frm.doc.name },
            callback: function (r) {
                if (!r.message || !r.message.success || !r.message.data) return;
                var s = r.message.data;
                var outstanding = flt(s.retention_outstanding);

                if (outstanding > 0.01) {
                    frm.dashboard.add_indicator(
                        __('Retention Outstanding: {0}',
                            [format_currency(outstanding, frm.doc.currency)]),
                        'orange'
                    );
                } else {
                    frm.dashboard.add_indicator(
                        __('All Retention Released ({0})',
                            [format_currency(flt(s.retention_amount), frm.doc.currency)]),
                        'green'
                    );
                }
            }
        });

        // ── 2. "Create → Retention Invoice" button ────────────────────────
        frm.add_custom_button(__('Retention Invoice'), function () {

            frappe.call({
                method: 'opentra_retention.api.get_invoice_retention_status',
                args: { sales_invoice: frm.doc.name },
                freeze: true,
                freeze_message: __('جاري التحقق من رصيد الاستقطاع...'),
                callback: function (r) {
                    if (!r.message || !r.message.success || !r.message.data) return;
                    var status = r.message.data;
                    var outstanding = flt(status.retention_outstanding);

                    // Block if nothing left to release
                    if (outstanding <= 0.01) {
                        frappe.msgprint({
                            title:     __('No Remaining Retention'),
                            message:   __(
                                'All retention (<b>{0}</b>) has already been released for invoice <b>{1}</b>.',
                                [
                                    format_currency(flt(status.retention_amount), frm.doc.currency),
                                    frm.doc.name
                                ]
                            ),
                            indicator: 'orange',
                        });
                        return;
                    }

                    // Open a new Retention Release (= Retention Invoice) pre-filled
                    frappe.new_doc('Retention Release', {
                        sales_invoice:  frm.doc.name,
                        customer:       frm.doc.customer,
                        company:        frm.doc.company,
                        release_date:   frappe.datetime.get_today(),
                        // release_amount is intentionally left empty — user fills manually
                    });
                }
            });

        }, __('Create'));

    }
});
