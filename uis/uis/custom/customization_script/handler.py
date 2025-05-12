import frappe

def validate(doc, method):
    if not doc.get("company") or doc.doctype in [
        "DocType", "Version", "Custom Field", "Property Setter", 
        "Portal Settings", "Installed Applications"
    ]:
        return

    meta_mandatory_field_dict = {}
    error_str = get_meta_info(doc, doc.company, meta_mandatory_field_dict)

    for df_name in doc.as_dict().keys():
        value = doc.get(df_name)
        if isinstance(value, list):
            for row in value:
                error_str += get_meta_info(row, doc.company, meta_mandatory_field_dict, is_for_childtable=True)

    if error_str:
        frappe.throw(error_str)


def get_meta_info(doc, company, meta_mandatory_field_dict={}, is_for_childtable=False):
    mandatory_field_list = ["branch", "cost_center", "department", "project"]
    error_str = ""
    meta_fields = frappe.get_meta(doc.doctype).fields

    for field in meta_fields:
        fieldname = field.get("fieldname")
        label = field.get("label") or fieldname
        options = field.get("options")

        if fieldname not in mandatory_field_list:
            continue

        value = doc.get(fieldname)

        # Case 1: Value missing
        if not value:
            prefix = f"{doc.doctype} : Row {getattr(doc, 'idx', 'N/A')}, " if is_for_childtable else ""
            error_str += f"{prefix}{frappe.bold(label)} is a mandatory field<br>"
            continue

        # Case 2: Invalid or missing options
        if not isinstance(options, str) or not options.strip():
            frappe.log_error(
                f"[Validation Skipped] Invalid or missing 'options' for field '{fieldname}' in doctype '{doc.doctype}'",
                "get_meta_info"
            )
            continue

        try:
            # Fetch valid values for the linked doctype and company
            if options not in meta_mandatory_field_dict:
                meta_mandatory_field_dict[options] = frappe.get_all(
                    options.strip(), filters={"company": company}, pluck="name"
                )

            if value not in meta_mandatory_field_dict[options]:
                prefix = f"{doc.doctype} : Row {getattr(doc, 'idx', 'N/A')}, " if is_for_childtable else ""
                error_str += f"{prefix}Incorrect value in {frappe.bold(label)} field<br>"

        except Exception as e:
            frappe.log_error(
                f"[Validation Error] Failed fetching from '{options}' for field '{fieldname}' in doctype '{doc.doctype}': {e}",
                "get_meta_info"
            )
            continue

    return error_str
