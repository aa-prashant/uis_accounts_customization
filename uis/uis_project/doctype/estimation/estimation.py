# Copyright (c) 2025, Mohamed Elyamany and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document

class Estimation(Document):
    def validate(self):
        self.total_employees = sum((row.total_amount or 0) for row in self.bidding_emp)
        self.total_assets = sum((row.total_amount or 0) for row in self.bidding_asset)
        self.total_operation = sum((row.total_amount or 0) for row in self.bidding_operation)
        self.total_miscellaneous = sum((row.total_amount or 0) for row in self.bidding_miscellaneous)
        self.total_subcontraction = sum((row.total_amount or 0) for row in self.bidding_subcontraction)
        self.total_bank_fee = sum((row.total_amount or 0) for row in self.bidding_bank_fee)
        self.total_additions = sum((row.addition or 0) for row in self.bidding_additions)

        base_amount = (
            self.total_employees +
            self.total_assets +
            self.total_operation +
            self.total_miscellaneous +
            self.total_subcontraction +
            self.total_bank_fee
        )
        self.amount_before_additions = base_amount

        additions_pct = self.total_additions or 0
        margin_pct = self.profit_margin or 0

        after_additions = base_amount + (base_amount * additions_pct / 100)
        self.amount_after_additions = after_additions

        self.profit_margin_value = after_additions * margin_pct / 100
        self.grand_total = after_additions + self.profit_margin_value

    def on_submit(self):
        if self.opportunity:
            html = frappe.render_template("templates/includes/estimation_html.html", {"doc": self})
            frappe.db.set_value("Opportunity", self.opportunity, "custom_estimation_html", html)


import frappe
from frappe.utils import flt

@frappe.whitelist()
def get_estimation_html(opportunity):
    estimation = frappe.get_all("Estimation", filters={
        "opportunity": opportunity,
        "docstatus": 1
    }, fields=["name"], order_by="modified desc", limit=1)

    if not estimation:
        return ""

    doc = frappe.get_doc("Estimation", estimation[0].name)

    def render_table(title, rows, columns):
        if not rows:
            return ""
        table_html = f"<h4>{title}</h4><table class='table table-bordered'><thead><tr>"
        for col in columns:
            table_html += f"<th>{col['label']}</th>"
        table_html += "</tr></thead><tbody>"
        for row in rows:
            table_html += "<tr>"
            for col in columns:
                value = row.get(col["fieldname"], "")
                value = flt(value) if isinstance(value, (int, float)) else value
                table_html += f"<td>{value}</td>"
            table_html += "</tr>"
        table_html += "</tbody></table>"
        return table_html

    sections = [
        {
            "title": "Employee Costs",
            "rows": doc.bidding_emp,
            "columns": [
                {"label": "Employee", "fieldname": "employee_name"},
                {"label": "Job Title", "fieldname": "job_title"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Cost to Company", "fieldname": "cost_to_company"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Assets",
            "rows": doc.bidding_asset,
            "columns": [
                {"label": "Asset", "fieldname": "asset_name"},
                {"label": "Branch", "fieldname": "branch"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Cost to Company", "fieldname": "cost_to_company"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Operations",
            "rows": doc.bidding_operation,
            "columns": [
                {"label": "Item", "fieldname": "item_name"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Price", "fieldname": "price"},
                {"label": "VAT %", "fieldname": "vat"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Miscellaneous",
            "rows": doc.bidding_miscellaneous,
            "columns": [
                {"label": "Item", "fieldname": "item_name"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Price", "fieldname": "price"},
                {"label": "VAT %", "fieldname": "vat"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Subcontraction",
            "rows": doc.bidding_subcontraction,
            "columns": [
                {"label": "Item", "fieldname": "item_name"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Price", "fieldname": "price"},
                {"label": "VAT %", "fieldname": "vat"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Bank Fees",
            "rows": doc.bidding_bank_fee,
            "columns": [
                {"label": "Item", "fieldname": "item_name"},
                {"label": "Qty", "fieldname": "qyt"},
                {"label": "Unit", "fieldname": "unit"},
                {"label": "Price", "fieldname": "price"},
                {"label": "VAT %", "fieldname": "vat"},
                {"label": "Total", "fieldname": "total_amount"},
            ]
        },
        {
            "title": "Additions",
            "rows": doc.bidding_additions,
            "columns": [
                {"label": "Item", "fieldname": "item_name"},
                {"label": "Addition (%)", "fieldname": "addition"},
            ]
        },
    ]

    html = f"""
    <div>
        <h3><b>Estimation Summary - {doc.name}</b></h3>
        <hr/>
        {''.join([render_table(section["title"], section["rows"], section["columns"]) for section in sections])}
        <h4>Final Totals</h4>
        <table class="table table-bordered">
            <tr><th>Total Employees</th><td>{flt(doc.total_employees)}</td></tr>
            <tr><th>Total Assets</th><td>{flt(doc.total_assets)}</td></tr>
            <tr><th>Total Operation</th><td>{flt(doc.total_operation)}</td></tr>
            <tr><th>Total Miscellaneous</th><td>{flt(doc.total_miscellaneous)}</td></tr>
            <tr><th>Total Subcontraction</th><td>{flt(doc.total_subcontraction)}</td></tr>
            <tr><th>Total Bank Fee</th><td>{flt(doc.total_bank_fee)}</td></tr>
            <tr><th>Amount Before Additions</th><td>{flt(doc.amount_before_additions)}</td></tr>
            <tr><th>Total Additions (%)</th><td>{flt(doc.total_additions)}</td></tr>
            <tr><th>Amount After Additions</th><td>{flt(doc.amount_after_additions)}</td></tr>
            <tr><th>Profit Margin (%)</th><td>{flt(doc.profit_margin)}</td></tr>
            <tr><th>Profit Margin Value</th><td>{flt(doc.profit_margin_value)}</td></tr>
            <tr><th><strong>Grand Total</strong></th><td><strong>{flt(doc.grand_total)}</strong></td></tr>
        </table>
    </div>
    """

    return html

