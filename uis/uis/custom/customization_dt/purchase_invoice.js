frappe.ui.form.on("Purchase Invoice", {
    validate:(frm)=>{
        item_tables = frm.doc.items 
        for(let item of item_tables){
            if(item.amount > item.custom_allocated_budget){
                frappe.throw("Amount cannot exceed then allocate budget.");
                
            }
        }
    }
})

frappe.ui.form.on("Purchase Invoice Item", {
    item_code:(frm)=>{
        frappe.call({
            method : "uis.uis.api.utils.get_allocated_amount",
            args : {"doc" : frm.doc, "selected_doc" : frm.selected_doc},
            callback:(response)=>{
                if(response.message){
                    frappe.model.set_value(cur_frm.selected_doc.doctype, cur_frm.selected_doc.name, "custom_allocated_budget", response.message)
                }
            }
        })
    }
})