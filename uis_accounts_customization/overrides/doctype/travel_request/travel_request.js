frappe.ui.form.on('Travel Request', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1) { // Check if the document is submitted
            frm.add_custom_button(__('Create Trip Request'), function () {
                frappe.new_doc('Trip Request', {
                    employee: frm.doc.employee,
                    employee_name: frm.doc.employee_name,
                    department: frm.doc.department,
                    designation: frm.doc.designation,
                    company: frm.doc.company,
                    purpose: frm.doc.purpose_of_travel,
                    project: frm.doc.project,
                })

            }, 'Create');
        }
    }
});

frappe.ui.form.on('Travel Request', {
    employee: function (frm) {
        if (frm.doc.employee) {
            frappe.db.get_value('Employee', frm.doc.employee, ['custom_iqama_number', 'custom_national_id_number'], (r) => {
                if (r.custom_iqama_number || r.custom_national_id_number) {
                    frm.set_value('personal_id_type', '');
                    frm.set_value('personal_id_number', '');
                }
            });
        }
    },
    personal_id_type: function (frm) {
        if (frm.doc.employee && frm.doc.personal_id_type) {
            frappe.db.get_value('Employee', frm.doc.employee, ['custom_iqama_number', 'custom_national_id_number'], (r) => {
                if (frm.doc.personal_id_type === 'Iqama No') {
                    frm.set_value('personal_id_number', r.custom_iqama_number);
                } else if (frm.doc.personal_id_type === 'National ID') {
                    frm.set_value('personal_id_number', r.custom_national_id_number);
                } else {
                    frm.set_value('personal_id_number', '');
                }
            });
        } else {
            frm.set_value('personal_id_number', '');
        }
    }
});
