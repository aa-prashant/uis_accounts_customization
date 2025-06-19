import frappe

from uis_accounts_customization.customization_script.budget import verify_validate_expense_against_budget, validate_budget_for_fixed_asset


def on_submit(doc, method):
    verify_validate_expense_against_budget(doc, doc.doctype)
