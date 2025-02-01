frappe.ui.form.on("Purchase Invoice Item", {
    item_code:(frm)=>{
        console.log("From Item code")
        frappe.call({
            method : "uis.uis.api.utils.get_allocated_amount",
            args : {"item_code" : frm.selected_doc.item_code},
            callback:(response)=>{
                if(response.message){
                    console.log(response.message)
                }
            }
        })
    }
})