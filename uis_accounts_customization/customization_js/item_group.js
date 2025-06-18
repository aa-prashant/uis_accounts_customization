
frappe.ui.form.on("Item Group", {
    refresh(frm){
        cur_frm.add_custom_button("Create Item", ()=>{
            create_item(frm)
        })
    }
})


function create_item(frm){
    fields = [
        {
            fieldtype: "Data",
            label: __("Item Name"),
            fieldname: "item_name",
            reqd: 1,
        },
        {
            fieldtype: "Link",
            label: __("Stock UOM"),
            fieldname: "stock_uom",
            reqd: 1,
            options:"UOM"
        }
    ]  
    frappe.prompt(
        fields,
        (value) => {
            validate_and_create_item(cur_frm, value.stock_uom, value.item_name)
        },
        "Create New Item Code",
        "Create"
    )
}


function validate_and_create_item(frm, stock_uom, value){
    frappe.call({
        method:"uis_accounts_customization.customization_script.item_group.validate_and_create_item",
        args:{"data" : value, "item_group_details" : frm.doc, "stock_uom" : stock_uom},
        callback:(r)=>{
            if(r.message.status){
                frappe.show_alert({
                    message: r.message.msg,
                    indicator: "green",
                });
            } 
            else {
                frappe.show_alert({
                    message: r.message.msg,
                    indicator: "red",
                });
            }
        }
    })
}