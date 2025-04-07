import frappe

def validate(doc, method):
    branch_list = company_branches(doc.company)
    if doc.branch not in branch_list:
        frappe.throw("Please select a valid branch")



def company_branches(company):
	branches = frappe.get_all("Branch", filters={"company": company}, pluck="name")
	return branches


