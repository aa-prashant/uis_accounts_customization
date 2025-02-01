// Copyright (c) 2025, Mohamed Elyamany and contributors
// For license information, please see license.txt

frappe.ui.form.on("Allocate Budget for Asset", {
	refresh(frm) {
        frm.fields_dict["table_qugr"].grid.get_field("item_code").get_query = function(doc, cdt, cdn) {
            let child = locals[cdt][cdn];  // Get the current row
            return {
                filters: {
                    is_fixed_asset: 1
                }
            };
        };
	},
});
