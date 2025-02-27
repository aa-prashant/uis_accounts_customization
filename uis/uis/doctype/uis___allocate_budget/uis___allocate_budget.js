// Copyright (c) 2025, Mohamed Elyamany and contributors
// For license information, please see license.txt

frappe.ui.form.on("UIS - Allocate Budget", {
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
        
	},
});
