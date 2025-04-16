import frappe
from uis.uis.custom.customization_script.budget import verify_validate_expense_against_budget, validate_budget_for_fixed_asset,  validate_expense_against_budget

@frappe.whitelist()
def validate_budget(doc = "", method = ""):
    for data in doc.get("items"):
        args = data.as_dict()
        args.update(
            {
                "doctype": doc.doctype,
                "company": doc.company,
                "posting_date": (
                    doc.schedule_date
                    if doc.doctype == "Material Request"
                    else doc.transaction_date
                ),
            }
        )
        validate_expense_against_budget(args)

