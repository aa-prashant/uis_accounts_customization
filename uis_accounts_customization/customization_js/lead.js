
frappe.ui.form.on('Lead', {
    setup(frm){
        frm.set_df_property("city", "reqd", 0) 
        frm.set_df_property("city", "hidden", 1) 
        frm.trigger("country");
        frm.trigger("custom_custom_state");
        
    },

    country(frm){
        let state_filters = {
            country : ['in' , frm.doc.country || null ]
        }
        if(frm.is_dirty()){
            frm.set_value("custom_custom_state", "")
        }
        uis_accounts_customization.utils.create_state_city_filter(frm, "custom_custom_state", state_filters)
    },

    custom_custom_state(frm){
        let city_filters = {
            state_province : ['in' , frm.doc.custom_custom_state || null ]
        }

        if(frm.is_dirty()){
            frm.set_value("custom_custom_city", "")
        }
        uis_accounts_customization.utils.create_state_city_filter(frm, "custom_custom_city", city_filters)
    },

    custom_custom_city(frm){

        if(frm.is_dirty()){
            frm.set_value("city", frm.doc.custom_custom_city)
        }

    }
})