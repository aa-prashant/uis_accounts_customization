import frappe

@frappe.whitelist()
def validate_and_create_item(data, stock_uom , item_group_details):
    item_name_tree_list = []
    item_name_tree_list.append(data)
    item_group = frappe._dict(frappe.parse_json(item_group_details))
    item_name_tree_list.append(item_group.item_group_name)
    item_name_tree_list.append(item_group.parent_item_group)

    item_group_name = frappe.db.get_value(item_group.doctype,item_group.parent_item_group, "parent_item_group")
    if item_group_name:
        item_name_tree_list.append(item_group_name)
    
    item_name_tree_list.reverse()
    new_item_name = ",".join(item_name_tree_list)
    item_doc = frappe.new_doc("Item")
    item_doc.item_code = new_item_name
    item_doc.item_name = new_item_name
    item_doc.item_group = item_name_tree_list[-2]
    item_doc.stock_uom  = stock_uom
    item_doc.is_stock_item = 0
    try:
        item_doc.save()
        url_str = f"<a href='{frappe.utils.get_url()}{item_doc.get_url()}'> {new_item_name} </a>"
        msg_with_list = f"{url_str} : Item is successfully created"
        return { "status" : True, "msg": msg_with_list}
    except Exception as e:
        error_doc = frappe.log_error("While Creating Item", e)
        url_str = f"<a href='{frappe.utils.get_url()}{error_doc.get_url()}'> Error </a>"
        msg_with_list = f"{url_str} : While Creating Item"
        return { "status" : False, "msg": msg_with_list }
