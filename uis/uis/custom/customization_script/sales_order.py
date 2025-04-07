import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

class OverrideSalesOrder(SalesOrder):
    def validate_update_after_submit(self):
        pass