import frappe
from uis.uis.api.utils import get_allocated_amount
from uis.uis.custom.customization_script.budget import verify_validate_expense_against_budget


def on_submit(doc, method):
    verify_validate_expense_against_budget(doc)
