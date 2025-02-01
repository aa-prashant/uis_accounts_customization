import frappe

@frappe.whitelist()
def get_allocated_amount(item_code=None):
    return True