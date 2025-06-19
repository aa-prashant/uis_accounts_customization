import frappe
from uis_accounts_customization.customization_script.budget import verify_validate_expense_against_budget, validate_budget_for_fixed_asset

def on_submit(doc, method):
    for item in doc.items:
        is_fixed_asset = frappe.db.get_value("Item", item.item_code, "is_fixed_asset")
        if is_fixed_asset:
            validate_budget_for_fixed_asset(doc, item.item_code, doc.branch)
    verify_validate_expense_against_budget(doc)
