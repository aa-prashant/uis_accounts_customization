# Copyright (c) 2024, Mohamed Elyamany and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, time_diff_in_hours

class JobOrder(Document):
    def validate(self):
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1 and self.status == "Draft":
            frappe.throw(_("Cannot keep status as 'Draft' once submitted."))

        if self.sales_order:
            sales_order = frappe.get_doc("Sales Order", self.sales_order)
            if self.docstatus == 0:
                self.status = "Submitted"  # Pre-set before submission (optional)

            for service in self.service_job_order:
                matching_item = next((item for item in sales_order.items if item.item_code == service.service_code), None)
                if not matching_item:
                    frappe.throw(_("Item {0} not found in Sales Order.").format(service.service_code))

                remaining_qty = (matching_item.qty or 0) - (matching_item.custom_job_order_qty or 0)
                if service.quantity > remaining_qty:
                    frappe.throw(_("Service Quantity for {item} exceeds remaining quantity in Sales Order.\nAvailable: {available}, Entered: {entered}")
                        .format(item=service.service_code, available=remaining_qty, entered=service.quantity))

    def before_submit(self):
        self.status = "Submitted"

    def on_submit(self):
        if self.sales_order:
            sales_order = frappe.get_doc("Sales Order", self.sales_order)
            for service in self.service_job_order:
                for item in sales_order.items:
                    if item.item_code == service.service_code:
                        item.custom_job_order_qty = (item.custom_job_order_qty or 0) + service.quantity
            sales_order.save(ignore_permissions=True)

    def on_update_after_submit(self):
        if self.status == "In Process":
            for row in self.asset_job_order:
                if not row.activity_start_at:
                    row.activity_start_at = now_datetime()

        elif self.status == "Completed":
            for row in self.asset_job_order:
                if not row.activity_ends_at:
                    row.activity_ends_at = now_datetime()

                if row.activity_start_at and row.activity_ends_at:
                    row.working_hours = time_diff_in_hours(row.activity_ends_at, row.activity_start_at)
                    asset_cost = frappe.db.get_value("Asset", row.asset_code, "custom_cost_to_company")
                    if asset_cost:
                        row.total_cost_incurred = row.working_hours * asset_cost
