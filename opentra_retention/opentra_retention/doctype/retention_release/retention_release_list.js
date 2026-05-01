frappe.listview_settings['Retention Release'] = {
    get_indicator: function(doc) {
        if (doc.status === 'Paid') {
            return [__('Paid'), 'green', 'status,=,Paid'];
        } else if (doc.status === 'Submitted') {
            return [__('Submitted'), 'blue', 'status,=,Submitted'];
        } else if (doc.status === 'Cancelled') {
            return [__('Cancelled'), 'red', 'status,=,Cancelled'];
        } else {
            return [__('Draft'), 'grey', 'status,=,Draft'];
        }
    }
};
