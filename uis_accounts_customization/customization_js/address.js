
frappe.ui.form.on('Address', {
    setup(frm){
        frm.set_df_property("city", "reqd", 0) 
        frm.set_df_property("city", "hidden", 1) 
        frm.trigger("country");
        frm.trigger("custom_state_province");
        
    },

    country(frm){
        let state_filters = {
            country : ['in' , frm.doc.country || null ]
        }
        if(frm.is_dirty()){
            frm.set_value("custom_state_province", "")
        }
        uis_accounts_customization.utils.create_state_city_filter(frm, "custom_state_province", state_filters)
    },

    custom_state_province(frm){
        let city_filters = {
            state_province : ['in' , frm.doc.custom_state_province || null ]
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