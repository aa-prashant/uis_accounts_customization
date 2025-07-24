import frappe

def db_insert(doc, method):
    """
    Triggered on Cost Center insert.
    Creates the same Cost Center for all child companies.
    """
    if not frappe.db.get_value("Cost Center",{"company" : doc.company ,"name":doc.parent_cost_center},['cost_center_name', "cost_center_number"]):
        frappe.throw("Please select a valid Parent Cost Center for this company.")

    # Get all child companies of the current doc's company
    child_company_list = frappe.get_all(
        "Company",
        filters={"parent_company": doc.company},
        fields=["name"]
    )

    if not child_company_list and not frappe.cache().get_value("is_parent_request_for_child_cc"):
        frappe.throw("Cannot create Cost Center Directly for Child company.")
    elif frappe.cache().get_value("is_parent_request_for_child_cc") is not None and frappe.cache().get_value("is_parent_request_for_child_cc") != doc.company:
        return True

    # frappe.cache().delete_value("is_parent_request_for_child_cc")

    frappe.cache().set_value("is_parent_request_for_child_cc", doc.company)
    # Create the cost center in each child company
    for child_company in child_company_list:
        create_cc_for_company(doc, child_company.name)


def create_cc_for_company(source_doc, target_company_name):
    """
    Create a Cost Center in the specified child company.
    """
    target_company = frappe.get_doc("Company", target_company_name)

    # Optional: Skip if already exists (avoid duplicates)
    exists = frappe.db.exists(
        "Cost Center",
        {
            "company": target_company.name,
            "cost_center_name": source_doc.cost_center_name
        }
    )
    if exists:
        return

    # Get the default parent cost center for this company, if defined
    parent_account = get_target_company_cc(source_doc, target_company.name)

    cc = frappe.new_doc("Cost Center")
    cc.company = target_company.name
    cc.cost_center_name = source_doc.cost_center_name
    cc.parent_cost_center = parent_account
    cc.is_group = source_doc.is_group  # replicate group/leaf type
    cc.disabled = source_doc.disabled
    cc.save()

def get_target_company_cc(source_doc, target_company):
    """
    Get the parent cost center for the target company.
    If not defined, return None.
    """
    # source_company_cc = frappe.db.get_value("Cost Center",source_doc.parent_cost_center,['cost_center_name', "cost_center_number"])

    
    # if not source_company_cc:
    #     return frappe.throw(f"Cost Center not found for company {source_doc.company}")
    
    
    # parent_cc = frappe.db.get_value(
    #     "Cost Center",
    #     {
    #         'cost_center_name' : source_company_cc.get('cost_center_name'),
    #         'cost_center_number' : source_company_cc.get('cost_center_number'),
    #     },
    #     ["name"]
    # )

    # return parent_cc
    company_mapped_cc = {
        "United Industrial Inspection Services Co. Ltd":"United Inspection Service - KSA - UIS-K",
        "United Inspection Service - EGP" : "United Inspection Service - EGP - UIS-E",
        "United Inspection Service - IND" : "United Inspection Service - IND - UIS-I",
    }

    return company_mapped_cc.get(target_company)