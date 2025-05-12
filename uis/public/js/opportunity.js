frappe.ui.form.on('Opportunity', {
    refresh(frm) {
        // Show the button only if it's a saved doc and type is "Bidding"
        if (!frm.is_new() && frm.doc.opportunity_type === "Bidding") {
            frm.add_custom_button(__('Create Estimation'), function () {
                frappe.new_doc('Estimation', {
                    opportunity: frm.doc.name
                });
            }, __('Actions'));
        }
    }
});

frappe.ui.form.on('Opportunity', {
    onload: function (frm) {
        if (frm.doc.docstatus === 1 || frm.doc.docstatus === 0) {
            frappe.call({
                method: 'uis.uis_project.doctype.estimation.estimation.get_estimation_html',
                args: {
                    opportunity: frm.doc.name
                },
                callback: function (r) {
                    if (r.message) {
                        frm.fields_dict.custom_estimation_html.$wrapper.html(r.message);
                    }
                }
            });
        }
    }
});
