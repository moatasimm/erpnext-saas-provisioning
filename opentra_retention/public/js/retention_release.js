// Retention Release — Client Script
// Adds: "Create → Payment Entry", "Print → Retention Invoice" buttons after Submit
// Shows retention balance info on the form header.

frappe.ui.form.on('Retention Release', {

    // ── onload: show intro with retention balance ─────────────────────────
    onload: function (frm) {
        if (frm.doc.sales_invoice && frm.is_new()) {
            retention_refresh_balance(frm);
        }
    },

    // ── refresh: buttons + balance indicator ─────────────────────────────
    refresh: function (frm) {

        // Balance indicator: fetch for all docs with a linked invoice
        // (includes new docs so balance is auto-populated on first load)
        if (frm.doc.sales_invoice && frm.is_new()) {
            retention_refresh_balance(frm);
        }

        // Draft: show intro hint
        if (frm.doc.docstatus === 0) {
            if (frm.doc.remaining_before_release > 0.01) {
                frm.set_intro(
                    __('Outstanding retention for this invoice: <b>{0}</b>',
                        [format_currency(frm.doc.remaining_before_release)]),
                    'blue'
                );
            }
        }

        // Submitted (Released / Paid): show action buttons
        if (frm.doc.docstatus === 1 && frm.doc.status !== 'Paid' && frm.doc.status !== 'Cancelled') {

            // ── Button: Create Payment Entry ─────────────────────────────
            frm.add_custom_button(__('Create Payment Entry'), function () {
                frappe.call({
                    method: 'opentra_retention.api.make_retention_payment_entry',
                    args: { retention_release: frm.doc.name },
                    freeze: true,
                    freeze_message: __('Creating payment entry...'),
                    callback: function (r) {
                        if (r.message && r.message.success && r.message.data && r.message.data.name) {
                            var pe_name = r.message.data.name;
                            frappe.msgprint({
                                title: __('Payment Entry Created'),
                                message: __(
                                    'Payment Entry <b>{0}</b> created in Draft mode.<br>'
                                    + 'You can adjust the amount for partial payment before saving.',
                                    [pe_name]
                                ),
                                indicator: 'green',
                            });
                            frappe.set_route('Form', 'Payment Entry', pe_name);
                        }
                    }
                });
            }, __('Create'));
        }

        // ── Button: Print Retention Invoice (always on submitted docs) ───
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Print Retention Invoice'), function () {
                var url = frappe.urllib.get_full_url(
                    '/printview?'
                    + 'doctype=' + encodeURIComponent('Retention Release')
                    + '&name='    + encodeURIComponent(frm.doc.name)
                    + '&format='  + encodeURIComponent('Retention Invoice')
                    + '&no_letterhead=0'
                    + '&_lang='   + (frappe.boot.lang || 'ar')
                );
                window.open(url, '_blank');
            }, __('Print'));
        }
    },

    // ── live recalculation when user changes release_amount ──────────────
    release_amount: function (frm) {
        var remaining_before = flt(frm.doc.remaining_before_release);
        var release          = flt(frm.doc.release_amount);
        frm.doc.remaining_after_release = remaining_before - release;
        frm.refresh_field('remaining_after_release');
    },

    // ── auto-load balance when invoice is selected ────────────────────────
    sales_invoice: function (frm) {
        if (frm.doc.sales_invoice && frm.is_new()) {
            retention_refresh_balance(frm);
        }
    }
});


/**
 * Fetch invoice retention status and populate read-only balance fields
 * on the form header as a dashboard indicator.
 * Always updates balance fields on draft docs so the user sees correct
 * values without any manual interaction.
 */
function retention_refresh_balance(frm) {
    frappe.call({
        method: 'opentra_retention.api.get_invoice_retention_status',
        args:   { sales_invoice: frm.doc.sales_invoice },
        callback: function (r) {
            if (!r.message || !r.message.success || !r.message.data) return;
            var s           = r.message.data;
            var outstanding = flt(s.retention_outstanding);
            var color       = outstanding > 0.01 ? 'orange' : 'green';
            var msg         = outstanding > 0.01
                ? __('Retention Outstanding on Invoice: {0}', [format_currency(outstanding)])
                : __('All Retention Released for Invoice');

            frm.dashboard.add_indicator(msg, color);

            // Refresh read-only balance fields ONLY for brand-new (unsaved) docs.
            // This prevents a race condition: if the async call returns after the user
            // saves, frm.is_new() is false and we skip the field assignment,
            // keeping the form clean (no "Not Saved" / dirty flag after save).
            if (frm.is_new()) {
                frm.doc.retention_amount         = flt(s.retention_amount);
                frm.doc.total_already_released   = flt(s.total_released);
                frm.doc.remaining_before_release = flt(s.retention_outstanding);
                frm.refresh_fields(['retention_amount', 'total_already_released', 'remaining_before_release']);
                // release_amount → user fills manually (do NOT auto-set)
                // remaining_after_release → recalculates only when user types release_amount
            }
        }
    });
}
