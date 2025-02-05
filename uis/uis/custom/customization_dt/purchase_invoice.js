frappe.ui.form.on("Purchase Invoice", {
    branch: function(frm) {
        frm.doc.items.forEach(item => {
            frappe.model.set_value(item.doctype, item.name, "branch", frm.doc.branch);
        });
    }
})

frappe.ui.form.on("Purchase Invoice Item", {
    item_code:(frm)=>{
        frappe.call({
            method : "uis.uis.api.utils.get_allocated_amount",
            args : {"doc" : frm.doc, "selected_doc" : frm.selected_doc},
            callback:(response)=>{
                frappe.model.set_value(cur_frm.selected_doc.doctype, cur_frm.selected_doc.name, "custom_allocated_budget", response.message)
            }
        })
    },
})