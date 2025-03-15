// Copyright (c) 2025, Mohamed Elyamany and contributors
// For license information, please see license.txt

frappe.ui.form.on("UIS - Budget", {
	setup(frm) {
        frm.set_query("branch", ()=>{
            return {
                filters :{
                    "company" : frm.doc.company
                }
            }
        })
        frm.set_query("cost_center", ()=>{
            return {
                filters :{
                    "company" : frm.doc.company
                }
            }
        })
        frm.set_query("project", ()=>{
            return {
                filters :{
                    "company" : frm.doc.company
                }
            }
        })
        frm.set_query("department", ()=>{
            return {
                filters :{
                    "company" : frm.doc.company
                }
            }
        })

        frm.set_query("workflow", ()=>{
            return {
                filters :{
                    "document_type" : "Purchase Invoice"
                }
            }
        })

        frm.set_query("account", "accounts", function () {
            return {
                filters: {
                    company: frm.doc.company,
                    report_type: "Profit and Loss",
                    is_group: 0,
                },
            };
        });


        frm.set_query("item_code", "fixed_assest", function () {
            return {
                filters: {
                    is_fixed_asset: 1,
                },
            };
        });

        
        frm.set_query("monthly_distribution", function () {
            return {
                filters: {
                    fiscal_year: frm.doc.fiscal_year
                },
            };
        });
        
    },
});

