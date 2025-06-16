frappe.ui.form.on("Purchase Invoice", {
    branch: function(frm) {
        frm.doc.items.forEach(item => {
            frappe.model.set_value(item.doctype, item.name, "branch", frm.doc.branch);
        });
    }
})

frappe.ui.form.on("Purchase Invoice Item", {

    expense_account(frm){
        if(! frm.selected_doc.expense_account || ! frm.doc.branch){
            frappe.model.set_value(frm.selected_doc.doctype, frm.selected_doc.name, "custom_allocated_budget", 0)
            return
        }
        frm.call({
            method:"uis.uis.custom.customization_script.budget.fetch_remaining_budget",
            args :{
                doc:frm.doc,
                expense_account : frm.selected_doc.expense_account, 
                branch : frm.doc.branch, 
                cost_center : frm.doc.cost_center, project : 
                frm.doc.project, department : frm.doc.department,

            },
            callback:(response)=>{
                if(response.message){
                    frappe.model.set_value(frm.selected_doc.doctype, frm.selected_doc.name, "custom_allocated_budget", response.message.remaining_budget)
                }
            }

        })
    },

    item_code(frm){
        
        frm.trigger("expense_account", frm.selected_doc.doctype, frm.selected_doc.name)

        if(! frm.doc.branch || ! frm.selected_doc.item_code){
            frappe.model.set_value(frm.selected_doc.doctype, frm.selected_doc.name, "custom_allocated_budget", 0)
            return
        }
        frm.call({
            method:"uis.uis.custom.customization_script.budget.fetch_remaining_budget_for_item",
            args :{
                doc:frm.doc, 
                branch : frm.doc.branch, 
                cost_center : frm.doc.cost_center, project : 
                frm.doc.project, department : frm.doc.department,
                item_code : frm.selected_doc.item_code 
            },
            callback:(response)=>{
                if(response.message){
                    frappe.model.set_value(frm.selected_doc.doctype, frm.selected_doc.name, "custom_allocated_budget", response.message.remaining_budget)
                }
            }

        })
    },

    branch(frm){
        frm.trigger("expense_account", frm.selected_doc.doctype, frm.selected_doc.name)
    }
})