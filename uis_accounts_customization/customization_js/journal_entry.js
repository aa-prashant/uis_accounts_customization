frappe.ui.form.on("Journal Entry", {
    onload: function(frm) {
        cur_frm.set_query('project', 'accounts', function(doc, cdt, cdn) {
            return {
                filters: {
                    'company':cur_frm.doc.company
                }
            };
        });
    }
})


