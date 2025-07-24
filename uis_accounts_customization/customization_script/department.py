import frappe


def db_insert(doc, method):
    """
    Triggered on Department insert.
    Creates the same Department for all child companies.
    """

    # Validate parent department (if any)
    # if doc.parent_department and not frappe.db.get_value(
    #     "Department",
    #     {"company": doc.company, "name": doc.parent_department},
    #     ["department_name"]
    # ):
    #     frappe.throw("Please select a valid Parent Department for this company.")

    # Get all child companies
    child_company_list = frappe.get_all(
        "Company",
        filters={"parent_company": doc.company},
        fields=["name"]
    )

    # Prevent direct department creation in child companies
    if not child_company_list and not frappe.cache().get_value("is_parent_request_for_child_dept"):
        frappe.throw("Cannot create Department directly for Child Company.")
    elif frappe.cache().get_value("is_parent_request_for_child_dept") is not None and \
        frappe.cache().get_value("is_parent_request_for_child_dept") != doc.company:
        return True

    # Mark current request to avoid recursion
    frappe.cache().set_value("is_parent_request_for_child_dept", doc.company)

    for child_company in child_company_list:
        create_department_for_company(doc, child_company.name)

    # Clear cache after processing (optional cleanup)
    frappe.cache().delete_value("is_parent_request_for_child_dept")


def create_department_for_company(source_doc, target_company):
    """
    Create a Department in the specified child company.
    """

    # Skip if already exists
    if frappe.db.exists("Department", {
        "company": target_company,
        "department_name": source_doc.department_name
    }):
        return

    # Try to find matching parent department in target company
    parent_dept = None
    if source_doc.parent_department:
        parent_dept = "All Departments"

    new_dept = frappe.new_doc("Department")
    new_dept.company = target_company
    new_dept.department_name = source_doc.department_name
    new_dept.parent_department = parent_dept
    new_dept.is_group = source_doc.is_group if hasattr(source_doc, "is_group") else 0
    new_dept.save()

    frappe.msgprint(f"New Department '{new_dept.name}' is created")
