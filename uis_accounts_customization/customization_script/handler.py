import frappe

def validate(doc, method):
    if not doc.get('company') or  doc.doctype in ['DocType', 'Version', 'Custom Field', "Property Setter", "Portal Settings", "Installed Applications"]:
        return
    
    doc_df_list = list(doc.as_dict().keys())
    
    meta_mandatory_field_dict = {}
    child_table_name_list = [ df_name for df_name in doc_df_list if isinstance(doc.get(df_name), list)]


    error_str = ""
    error_str = get_meta_info(doc,doc.company, meta_mandatory_field_dict)

    for df_name in child_table_name_list:
        for row in doc.get(df_name):
            error_str += get_meta_info(row,doc.company, meta_mandatory_field_dict, 1)

    if error_str:
        frappe.throw(error_str)
    

def get_meta_info(doc, company, meta_mandatory_field_dict = {}, is_for_childtable = False):

    mandatory_field_list = ['branch', "cost_center", "department", "project"]
    error_str = ""
    meta_df_list = frappe.get_meta(doc.doctype).fields

    for meta_field in meta_df_list:
        if meta_field.fieldtype == "Data":
            continue
        if meta_field.get("fieldname") in mandatory_field_list:
            
            if not doc.get(meta_field.get("fieldname")):
                if is_for_childtable:
                    error_str += f'{doc.doctype} : Row {doc.idx}, {frappe.bold(meta_field.get("label"))} is a mandatory field<br>'
                else:
                    error_str += f'{frappe.bold(meta_field.get("label"))} is a mandatory field<br>'

            else:
                if meta_field.get("options") not in meta_mandatory_field_dict:
                    get_all_doc_record =  frappe.get_all(meta_field.get("options"), {"company" :company}, pluck = "name")
                    meta_mandatory_field_dict[meta_field.get("options")] = get_all_doc_record
                else :
                    get_all_doc_record = meta_mandatory_field_dict[meta_field.get("options")]
                if doc.get(meta_field.get("fieldname")) not in get_all_doc_record:
                    if is_for_childtable:
                        error_str += f'{doc.doctype} : Row {doc.idx}, Incorrect value in  {frappe.bold(meta_field.get("label"))} field<br>'
                    else:
                        error_str += f'Incorrect value in {frappe.bold(meta_field.get("label"))} field<br>'

    return error_str
