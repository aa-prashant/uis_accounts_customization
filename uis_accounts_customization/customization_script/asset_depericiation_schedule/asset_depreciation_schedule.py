import frappe

def before_insert(doc, method):
    asset = doc.asset
    if asset:
        doc.department = frappe.db.get_value("Asset", asset, "department")
        doc.branch = frappe.db.get_value("Asset", asset, "branch")