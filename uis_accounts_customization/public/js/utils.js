frappe.provide("uis_accounts_customization.utils");

$.extend(uis_accounts_customization.utils, {
    create_state_city_filter(frm, fieldName, filter_obj){
        frm.set_query(fieldName, ()=>{
            return  {
                filters:filter_obj
            }
        })
    }
})