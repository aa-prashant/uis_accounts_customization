import frappe

def before_insert(doc, method):
    for asset_row in doc.assets:
        asset = asset_row.asset
        department_name = frappe.db.get_value("Asset",asset, "department")
        asset_row.department = department_name
