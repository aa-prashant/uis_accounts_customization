import frappe
from uis.uis.api.utils import get_allocated_amount

def validate(doc, method):
    for item in doc.items:
        is_fixed_asset = frappe.db.get_value("Item",item.item_code, "is_fixed_asset" )
        if is_fixed_asset:
            allocated_left_budget = get_allocated_amount(doc, item)
            if allocated_left_budget < item.amount:
                frappe.throw(f"Amount cannot exceed then allocate budget.<br> For Item : {frappe.bold(item.item_code)}  in row no. {item.idx}.")
        else: return True
