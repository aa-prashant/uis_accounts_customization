import frappe
from frappe.utils import getdate

@frappe.whitelist()
def get_allocated_amount(doc, selected_doc=None):
    

    doc = frappe.parse_json(doc)
    doc = frappe._dict(doc)

    selected_doc = frappe.parse_json(selected_doc)
    selected_doc = frappe._dict(selected_doc)

    if not bool(selected_doc.item_code):
        return True
    
    fiscal_year = get_fiscal_year(doc.posting_date)

    selected_branch = selected_doc.branch
    branch = doc.branch
   
    if not bool(branch) and not bool(selected_branch):
        frappe.throw("Branch cannot be empty")
    elif bool(selected_branch) and branch != selected_branch:
        branch = selected_branch

    filters = {
        
        "branch" : branch,
        "company" : doc.company,
        "docstatus" : 1
    }
    budget_name = frappe.get_value("Allocate Budget for Asset", filters, "name")
    if not bool(budget_name):
        return True
    
    filters = {
        "parent":budget_name,
        "item_code" : selected_doc.item_code
    }

    get_allocated_budget = frappe.get_value("Budget Item",filters, ["budget_amount"])
    return get_allocated_budget


def get_fiscal_year(date):
    fiscal_year = frappe.get_doc("Fiscal Year", 
                                    {"year_start_date": ["<=", date], "year_end_date": [">=", date]}, 
                                    "title")
    return fiscal_year.get_formatted(fiscal_year.name)

@frappe.whitelist()
def fetch_fiscal_year(purchase_invoice):
    doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
    return get_fiscal_year(doc.posting_date)  # or doc.transaction_date
