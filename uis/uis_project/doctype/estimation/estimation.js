// Copyright (c) 2025, Mohamed Elyamany and contributors
// For license information, please see license.txt

frappe.ui.form.on('Estimation', {
    refresh(frm) {
        calculate_all_totals(frm);
    },
    total_additions(frm) {
        calculate_grand_totals(frm);
    },
    profit_margin(frm) {
        calculate_grand_totals(frm);
    }
});

function calculate_all_totals(frm) {
    calculate_table_total(frm, 'bidding_emp', 'qyt', 'cost_to_company', 'total_amount', 'total_employees');
    calculate_table_total(frm, 'bidding_asset', 'qyt', 'cost_to_company', 'total_amount', 'total_assets');
    calculate_table_total(frm, 'bidding_operation', 'qyt', 'price', 'total_amount', 'total_operation', true);
    calculate_table_total(frm, 'bidding_miscellaneous', 'qyt', 'price', 'total_amount', 'total_miscellaneous', true);
    calculate_table_total(frm, 'bidding_subcontraction', 'qyt', 'price', 'total_amount', 'total_subcontraction', true);
    calculate_table_total(frm, 'bidding_bank_fee', 'qyt', 'price', 'total_amount', 'total_bank_fee', true);
    calculate_additions_total(frm);
    calculate_grand_totals(frm);
}

function calculate_table_total(frm, table_field, qty_field, rate_field, total_field, parent_total_field, has_vat = false) {
    const rows = frm.doc[table_field] || [];
    let total = 0.0;

    rows.forEach(row => {
        const qty = flt(row[qty_field] || 0);
        const rate = flt(row[rate_field] || 0);
        const vat = has_vat ? flt(row.vat || 0) : 0.0;

        const subtotal = qty * rate;
        const row_total = subtotal + (subtotal * vat / 100);

        frappe.model.set_value(row.doctype, row.name, total_field, row_total);

        total += row_total;
    });

    frm.set_value(parent_total_field, total);
}

function calculate_additions_total(frm) {
    const rows = frm.doc.bidding_additions || [];
    let total_additions = 0.0;

    rows.forEach(row => {
        total_additions += flt(row.addition || 0);
    });

    frm.set_value('total_additions', total_additions);
}

function calculate_grand_totals(frm) {
    const base_fields = [
        'total_employees', 'total_assets', 'total_operation',
        'total_miscellaneous', 'total_subcontraction', 'total_bank_fee'
    ];

    const base_amount = base_fields.reduce((acc, field) => acc + flt(frm.doc[field] || 0), 0);
    frm.set_value('amount_before_additions', base_amount);

    const additions = flt(frm.doc.total_additions || 0);
    const additions_value = base_amount * additions / 100;
    const after_additions = base_amount + additions_value;
    frm.set_value('amount_after_additions', after_additions);

    const margin = flt(frm.doc.profit_margin || 0);
    const margin_value = after_additions * margin / 100;
    const grand_total = after_additions + margin_value;

    frm.set_value('profit_margin_value', margin_value);
    frm.set_value('grand_total', grand_total);
}

frappe.ui.form.on('Bidding Emp', {
    qyt: calculate_all_totals,
    cost_to_company: calculate_all_totals
});

frappe.ui.form.on('Bidding Asset', {
    qyt: calculate_all_totals,
    cost_to_company: calculate_all_totals
});

frappe.ui.form.on('Bidding Operation', {
    qyt: calculate_all_totals,
    price: calculate_all_totals,
    vat: calculate_all_totals
});

frappe.ui.form.on('Bidding Miscellaneous', {
    qyt: calculate_all_totals,
    price: calculate_all_totals,
    vat: calculate_all_totals
});

frappe.ui.form.on('Bidding Subcontraction', {
    qyt: calculate_all_totals,
    price: calculate_all_totals,
    vat: calculate_all_totals
});

frappe.ui.form.on('Bidding Bank Fee', {
    qyt: calculate_all_totals,
    price: calculate_all_totals,
    vat: calculate_all_totals
});

frappe.ui.form.on('Bidding Additions', {
    addition: calculate_all_totals
});

frappe.ui.form.on('Bidding Asset', {
    asset_name: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.asset_name) {
            frappe.db.get_value('Asset', row.asset_name, 'custom_branch')
                .then(res => {
                    frappe.model.set_value(cdt, cdn, 'branch', res.message.custom_branch);
                });
        }
    }
});
