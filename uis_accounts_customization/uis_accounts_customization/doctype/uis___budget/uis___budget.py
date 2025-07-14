# Copyright (c) 2025, Mohamed Elyamany and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class UISBudget(Document):
	def validate(self):

		if not self.accounts and not self.fixed_assest:
			frappe.throw("UIS - Budget need to be create aganist Account or Fixed Asset")

		doc_filter = {
			"branch" : self.branch,
			"cost_center" : self.cost_center,
			"project" : self.project,
			"department" : self.department,
			"name" : ["!=", self.name],
			"docstatus" : ["!=", 2]
		}

		another_budget_doc_name_list = frappe.get_all("UIS - Budget", doc_filter, pluck="name")
		error_str = ""
		for another_doc_name in another_budget_doc_name_list:
			if self.accounts:
				another_budget_doc_name_list = frappe.get_all("Budget Account", {'parent' : another_doc_name}, pluck="account")
				
				if another_budget_doc_name_list:
					for accounts in self.accounts:
						if accounts.account in another_budget_doc_name_list:
							error_str += f"Row No. {accounts.idx} :Account {frappe.bold(accounts.account)} repeat with UIS - Budget ID {frappe.bold(another_doc_name)} <br>"

			if self.fixed_assest:
				another_budget_doc_name_list = frappe.get_all("Budget Item", {'parent' : another_doc_name}, pluck="item_code")
				if another_budget_doc_name_list:
					for fixed_asset in self.fixed_assest:
						if fixed_asset.item_code in another_budget_doc_name_list:
							error_str += f"Row No. {fixed_asset.idx} : Fixed Asset {frappe.bold(fixed_asset.item_code)} repeat with UIS - Budget ID {frappe.bold(another_doc_name)} <br>"

		accounts_list = frappe.get_all("Account", {"company": self.company}, pluck="name")
		for account in self.accounts:
			if account.account not in accounts_list:
				frappe.throw(f"Row No. {account.idx} : Account {frappe.bold(account.account)} not found in company {frappe.bold(self.company)}")
				
		if error_str:
			frappe.throw(error_str)
		return another_budget_doc_name_list
