frappe.ui.form.on("Sales Invoice", {
    refresh: function(frm) {
       frm.set_query('project',function(doc, cdt, cdn) {
            return {
                filters: {
                    'company':cur_frm.doc.company,
                    'customer': frm.doc.customer,
                }
            };
        });
    }
})