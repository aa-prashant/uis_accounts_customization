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
    
    selected_branch = selected_doc.branch
    branch = doc.branch
   
    if not bool(branch) and not bool(selected_branch):
        frappe.throw("Branch cannot be empty")
    elif bool(selected_branch) and branch != selected_branch:
        branch = selected_branch

    allocated_budget = get_allocated_budget(doc, selected_doc, branch)
    pi_item_amount = get_used_budget(doc, selected_doc)
    return allocated_budget - pi_item_amount

def get_fiscal_year(date):
    fiscal_year = frappe.get_doc("Fiscal Year", 
                                    {"year_start_date": ["<=", date], "year_end_date": [">=", date]}, 
                                    "title")
    return fiscal_year.get_formatted(fiscal_year.name)

@frappe.whitelist()
def fetch_fiscal_year(purchase_invoice):
    doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
    return get_fiscal_year(doc.posting_date)  # or doc.transaction_date

def get_allocated_budget(doc, selected_doc, branch):
    fiscal_year = get_fiscal_year(doc.posting_date)


    filters = {
        
        "branch" : branch,
        "company" : doc.company,
        "docstatus" : 1
    }
    budget_name = frappe.get_value("Allocate Budget for Asset", filters, "name")
    if not bool(budget_name):
        return 0
    
    filters = {
        "parent":budget_name,
        "item_code" : selected_doc.item_code
    }

    allocated_budget = frappe.get_value("Budget Item",filters, ["budget_amount"])
    return allocated_budget if allocated_budget is not None else 0

def get_used_budget(doc, selected_doc):
    filters = {'item_code' : selected_doc.item_code, 
               "docstatus" : 1
            }
    pi_item = frappe.get_value("Purchase Invoice Item", filters , "amount")
    return pi_item if pi_item is not None else 0

