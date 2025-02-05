import frappe
from frappe.utils import getdate

@frappe.whitelist()
def get_allocated_amount(doc, selected_doc=None):
    doc = frappe._dict(frappe.parse_json(doc)) if type(doc) == str else doc
    selected_doc = frappe._dict(frappe.parse_json(selected_doc))  if type(selected_doc) == str else selected_doc

    if not selected_doc.get("item_code"):
        return 0
    
    branch = selected_doc.get("branch") or doc.get("branch")

    if not branch:
        frappe.throw("Branch cannot be empty")

    allocated_budget = get_allocated_budget(doc, selected_doc, branch)
    pi_item_amount = get_used_budget(doc, selected_doc, branch)
    
    return allocated_budget - pi_item_amount

@frappe.whitelist()
def get_fiscal_year(doc):
    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": ["<=", doc.posting_date], "year_end_date": [">=", doc.posting_date]},
        pluck="name"
    )

    return next(
        (fy for fy in fiscal_years if frappe.db.exists("Fiscal Year Company", {"parent": fy, "company": doc.company})),
        None
    )

def get_allocated_budget(doc, selected_doc, branch):
    fiscal_year = get_fiscal_year(doc)
    if not fiscal_year:
        return 0
    
    budget_name = frappe.get_value(
        "Allocate Budget for Asset",
        {"fiscal_year": fiscal_year, "branch": branch, "company": doc.company, "docstatus": 1},
        "name"
    )
    
    if not budget_name:
        return 0

    allocated_budget = frappe.get_value(
        "Budget Item",
        {"parent": budget_name, "item_code": selected_doc.item_code},
        "budget_amount"
    )

    return allocated_budget or 0

def get_used_budget(doc, selected_doc, branch):
    fiscal_year = get_fiscal_year(doc)
    if not fiscal_year:
        return 0
    filters = {
                "item_code" : selected_doc.item_code, 
                "docstatus" : 1,
                "branch" : selected_doc.branch
            }
    pi_item = frappe.db.get_values("Purchase Invoice Item", filters , ["parent", "amount"], as_dict = True)
    used_amount = 0
    for item in pi_item:
        pi_parent_obj = frappe.get_value("Purchase Invoice", item.parent, ["posting_date", "company", "branch"], as_dict=True)

        if doc.company != pi_parent_obj.company and branch != pi_parent_obj.branch:
            continue
        item_parent_fy_year = get_fiscal_year(frappe._dict({"posting_date" : pi_parent_obj.get('posting_date'), "company":pi_parent_obj.company}))
        if fiscal_year == item_parent_fy_year:
            used_amount +=item.amount
    return used_amount

