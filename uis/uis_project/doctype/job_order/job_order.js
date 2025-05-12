// Copyright (c) 2024, Mohamed Elyamany and contributors
// For license information, please see license.txt

frappe.ui.form.on("Job Order", {
    onload: function (frm) {
        if (frm.is_new()) {
            frm.set_value("status", "Draft");
        }
    },

    sales_order: function (frm) {
        if (!frm.doc.sales_order) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Sales Order",
                name: frm.doc.sales_order
            },
            callback: function (r) {
                if (!r.message || !r.message.items) return;

                frm.clear_table("service_job_order");

                r.message.items.forEach(item => {
                    let remaining_qty = (item.qty || 0) - (item.custom_job_order_qty || 0);
                    if (remaining_qty > 0) {
                        frm.add_child("service_job_order", {
                            service_code: item.item_code,
                            service_name: item.item_name,
                            service_category: item.item_group,
                            quantity: remaining_qty
                        });
                    }
                });

                frm.refresh_field("service_job_order");
            }
        });
    },

    status: function (frm) {
        if (frm.doc.docstatus === 1) {
            if (!["In Process", "Completed"].includes(frm.doc.status)) {
                frappe.throw(__("After submission, only 'In Process' or 'Completed' status is allowed."));
            }
        }
    }
});
