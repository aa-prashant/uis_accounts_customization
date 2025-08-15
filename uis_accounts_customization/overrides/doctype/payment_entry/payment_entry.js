// Custom Script: Payment Entry
function set_party_query(frm) {
    frm.set_query('party', () => {
        if (!frm.doc.company) return {};
        return { filters: { company: frm.doc.company } }; // server reads this
    });
}

frappe.ui.form.on('Payment Entry', {
    onload(frm) {
        set_party_query(frm);
    },
    refresh(frm) {
        set_party_query(frm);
    },
    party_type(frm) {
        // core may overwrite set_query on party_type change → set again
        set_party_query(frm);
    },
    company(frm) {
        // if user changes company, push new filter value
        set_party_query(frm);
    }
});