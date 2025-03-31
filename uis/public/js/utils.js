frappe.provide("uis.utils");

$.extend(uis.utils, {
    create_state_city_filter(frm, fieldName, filter_obj){
        frm.set_query(fieldName, ()=>{
            return  {
                filters:filter_obj
            }
        })
    }
})