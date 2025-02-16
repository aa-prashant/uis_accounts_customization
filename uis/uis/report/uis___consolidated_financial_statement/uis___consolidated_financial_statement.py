# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from collections import defaultdict

import frappe
from frappe.utils import cstr
from frappe import _
from frappe.query_builder import Criterion
from frappe.utils import flt, getdate

import erpnext
from erpnext.accounts.report.balance_sheet.balance_sheet import (
	get_chart_data,
	get_provisional_profit_loss,
)
from erpnext.accounts.report.balance_sheet.balance_sheet import (
	get_report_summary as get_bs_summary,
)
from erpnext.accounts.report.cash_flow.cash_flow import (
	add_total_row_account,
	get_cash_flow_accounts,
)
from erpnext.accounts.report.cash_flow.cash_flow import get_report_summary as get_cash_flow_summary
from erpnext.accounts.report.financial_statements import (
	filter_out_zero_value_rows,
	get_fiscal_year_data,
	sort_accounts,
)
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
	get_chart_data as get_pl_chart_data,
)
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
	get_net_profit_loss,
)
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
	get_report_summary as get_pl_summary,
)
from erpnext.accounts.report.utils import convert, convert_to_presentation_currency

from erpnext.accounts.report.financial_statements import get_cost_centers_with_children

def execute(filters=None):
	columns, data, message, chart = [], [], [], []

	if not filters.get("company"):
		return columns, data, message, chart

	fiscal_year = get_fiscal_year_data(filters.get("from_fiscal_year"), filters.get("to_fiscal_year"))
	companies_column, companies = get_companies(filters)
	columns = get_columns(companies_column, filters)
	is_pnl = False
	if filters.get("report") == "Balance Sheet":
		data, message, chart, report_summary = get_balance_sheet_data(
			fiscal_year, companies, columns, filters
		)
	elif filters.get("report") == "Profit and Loss Statement":
		data, message, chart, report_summary = get_profit_loss_data(fiscal_year, companies, columns, filters)
		is_pnl = True
	else:
		data, report_summary = get_cash_flow_data(fiscal_year, companies, filters)
	
	columns = get_columns_branch_wise(companies_column, filters, is_pnl)
	data = formated_data_list(data, is_pnl)
	return columns, data, message, chart, report_summary


def get_balance_sheet_data(fiscal_year, companies, columns, filters):
	
	branches, company_fetched_list = [], []
	data_list, report_summary_list = [], []
	for key in companies:
		for company in companies[key]:
			if company in company_fetched_list:
				continue
			company_fetched_list.append(company)
			branches = company_branches(company)
			
			for branch in branches:
				key = (company, branch)
				data, message, chart, report_summary = get_balance_sheet_data_branch(fiscal_year, companies, columns, filters, branch)
				report_summary_list = calculate_report_summary(report_summary, report_summary_list)
				data_list.append({key: data})
	return data_list, message, chart, report_summary_list

def get_balance_sheet_data_branch(fiscal_year, companies, columns, filters, branch):
	asset = get_data(companies, "Asset", "Debit", fiscal_year, filters=filters, branch=branch)

	liability = get_data(companies, "Liability", "Credit", fiscal_year, filters=filters, branch=branch)

	equity = get_data(companies, "Equity", "Credit", fiscal_year, filters=filters, branch=branch)

	data = []
	data.extend(asset or [])
	data.extend(liability or [])
	data.extend(equity or [])

	company_currency = get_company_currency(filters)
	provisional_profit_loss, total_credit = get_provisional_profit_loss(
		asset, liability, equity, companies, filters.get("company"), company_currency, True
	)

	message, opening_balance = prepare_companywise_opening_balance(asset, liability, equity, companies)

	if opening_balance:
		unclosed = {
			"account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"warn_if_negative": True,
			"currency": company_currency,
		}

		for company in companies:
			unclosed[company] = opening_balance.get(company)
			if provisional_profit_loss and provisional_profit_loss.get(company):
				provisional_profit_loss[company] = flt(provisional_profit_loss[company]) - flt(
					opening_balance.get(company)
				)

		unclosed["total"] = opening_balance.get(company)
		data.append(unclosed)

	if provisional_profit_loss:
		data.append(provisional_profit_loss)
	if total_credit:
		data.append(total_credit)

	report_summary, primitive_summary = get_bs_summary(
		companies,
		asset,
		liability,
		equity,
		provisional_profit_loss,
		company_currency,
		filters,
		True,
	)

	chart = get_chart_data(filters, columns, asset, liability, equity, company_currency)

	return data, message, chart, report_summary


def prepare_companywise_opening_balance(asset_data, liability_data, equity_data, companies):
	opening_balance = {}
	for company in companies:
		opening_value = 0

		# opening_value = Aseet - liability - equity
		for data in [asset_data, liability_data, equity_data]:
			if data:
				account_name = get_root_account_name(data[0].root_type, company)
				if account_name:
					opening_value += get_opening_balance(account_name, data, company) or 0.0

		opening_balance[company] = opening_value

	if opening_balance:
		return _("Previous Financial Year is not closed"), opening_balance

	return "", {}


def get_opening_balance(account_name, data, company):
	for row in data:
		if row.get("account_name") == account_name:
			return row.get("company_wise_opening_bal", {}).get(company, 0.0)


def get_root_account_name(root_type, company):
	root_account = frappe.get_all(
		"Account",
		fields=["account_name"],
		filters={
			"root_type": root_type,
			"is_group": 1,
			"company": company,
			"parent_account": ("is", "not set"),
		},
		as_list=1,
	)

	if root_account:
		return root_account[0][0]


def get_profit_loss_data(fiscal_year, companies, columns, filters):

	branches, company_fetched_list = [], []
	data_list, report_summary_list = [], []
	for key in companies:
		for company in companies[key]:
			if company in company_fetched_list:
				continue
			company_fetched_list.append(company)
			branches = company_branches(company)
			
			for branch in branches:
				key = (company, branch)
				data, message, chart, report_summary = get_profit_loss_data_branch_wise(fiscal_year, companies, columns, filters, branch)
				data_list.append({key:data})
	return data_list, message, chart, report_summary 

def get_profit_loss_data_branch_wise(fiscal_year, companies, columns, filters, branch):
	income, expense, net_profit_loss = get_income_expense_data(companies, fiscal_year, filters, branch)
	company_currency = get_company_currency(filters)

	data = []
	data.extend(income or [])
	data.extend(expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	chart = get_pl_chart_data(filters, columns, income, expense, net_profit_loss, company_currency)

	report_summary, primitive_summary = get_pl_summary(
		companies, "", income, expense, net_profit_loss, company_currency, filters, True
	)

	return data, None, chart, report_summary


def get_income_expense_data(companies, fiscal_year, filters, branch):
	company_currency = get_company_currency(filters)
	income = get_data(companies, "Income", "Credit", fiscal_year, filters, True, branch)

	expense = get_data(companies, "Expense", "Debit", fiscal_year, filters, True, branch)

	net_profit_loss = get_net_profit_loss(income, expense, companies, filters.company, company_currency, True)

	return income, expense, net_profit_loss


def get_cash_flow_data(fiscal_year, companies, filters):

	branches, company_fetched_list = [], []
	data_list, report_summary_list = [], []
	for key in companies:
		for company in companies[key]:
			if company in company_fetched_list:
				continue
			company_fetched_list.append(company)
			branches = company_branches(company)
			
			for branch in branches:
				key = (company, branch)
				data, report_summary = get_cash_flow_data_base_branch(fiscal_year, companies, filters, branch)
				data_list.append({key:data})
				report_summary_list.append(report_summary)
	return data_list, report_summary


def get_cash_flow_data_base_branch(fiscal_year, companies, filters, branch):
	cash_flow_accounts = get_cash_flow_accounts()

	income, expense, net_profit_loss = get_income_expense_data(companies, fiscal_year, filters, branch )

	data = []
	summary_data = {}
	company_currency = get_company_currency(filters)

	for cash_flow_account in cash_flow_accounts:
		section_data = []
		data.append(
			{
				"account_name": cash_flow_account["section_header"],
				"parent_account": None,
				"indent": 0.0,
				"account": cash_flow_account["section_header"],
			}
		)

		if len(data) == 1:
			# add first net income in operations section
			if net_profit_loss:
				net_profit_loss.update(
					{"indent": 1, "parent_account": cash_flow_accounts[0]["section_header"]}
				)
				data.append(net_profit_loss)
				section_data.append(net_profit_loss)

		for account in cash_flow_account["account_types"]:
			account_data = get_account_type_based_data(
				account["account_type"], companies, fiscal_year, filters
			)
			account_data.update(
				{
					"account_name": account["label"],
					"account": account["label"],
					"indent": 1,
					"parent_account": cash_flow_account["section_header"],
					"currency": company_currency,
				}
			)
			data.append(account_data)
			section_data.append(account_data)

		add_total_row_account(
			data,
			section_data,
			cash_flow_account["section_footer"],
			companies,
			company_currency,
			summary_data,
			filters,
			True,
		)

	add_total_row_account(
		data, data, _("Net Change in Cash"), companies, company_currency, summary_data, filters, True
	)

	report_summary = get_cash_flow_summary(summary_data, company_currency)

	return data, report_summary


def get_account_type_based_data(account_type, companies, fiscal_year, filters):
	data = {}
	total = 0
	filters.account_type = account_type
	filters.start_date = fiscal_year.year_start_date
	filters.end_date = fiscal_year.year_end_date

	for company in companies:
		amount = get_account_type_based_gl_data(company, filters)

		if amount and account_type == "Depreciation":
			amount *= -1

		total += amount
		data.setdefault(company, amount)

	data["total"] = total
	return data


def get_columns(companies, filters):
	columns = [
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 300,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Data",
			"default":1
		},
	]

	for company in companies:
		apply_currency_formatter = 1 if not filters.presentation_currency else 0
		currency = filters.presentation_currency
		if not currency:
			currency = erpnext.get_company_currency(company)

		columns.append(
			{
				"fieldname": company,
				"label": f"{company} ({currency})",
				"fieldtype": "Currency",
				"options": "currency",
				"width": 150,
				"apply_currency_formatter": apply_currency_formatter,
				"company_name": company,
			}
		)

	return columns


def get_columns_branch_wise(companies, filters, is_pnl = False):

	columns = [
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 300,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		}
	]

	branches, company_fetched_list = [], []
	
	for company in companies:
		if company in company_fetched_list:
				continue
		company_fetched_list.append(company)
		branches = company_branches(company)
		
		for branch in branches:
			apply_currency_formatter = 1 if not filters.presentation_currency else 0
			currency = filters.presentation_currency
			if not currency:
				currency = erpnext.get_company_currency(company)

			columns.append(
				{
					"fieldname": f"{branch}_{company}",
					"label": f"{branch} - ({currency})",
					"fieldtype": "Currency",
					"options": "currency",
					"width": 150,
					"apply_currency_formatter": apply_currency_formatter,
					"company_name": company,
				}
			)
			if is_pnl:
				columns.append(
					{
						"fieldname": f"{branch}_{company}",
						"label": f"Estimated {branch} - ({currency})",
						"fieldtype": "Currency",
						"options": "currency",
						"width": 150,
						"apply_currency_formatter": apply_currency_formatter,
						"company_name": company,
					}
				)

				columns.append(
					{
						"fieldname": f"{branch}_{company}",
						"label": f"Utilized {branch} - ({currency})",
						"fieldtype": "Currency",
						"options": "currency",
						"width": 150,
						"apply_currency_formatter": apply_currency_formatter,
						"company_name": company,
					}
				)
	return columns

def formated_data_list(data_list, is_pnl=False):
	data = []
	data_list_account_name = {}
	for row in data_list:
		for key, item in row.items():
			branch_key = f"{key[1]}_{key[0]}"
			if len(data) < 1:
				for index,element in enumerate(item):
					if key[0] in element:
						element.update({branch_key : element[key[0]], "index" :index })
						data_list_account_name.update({element.get('account_name') : element})
				data = item
				continue
			for index, element in enumerate(item):
				if "total" in element:
					account_name = element.get('account_name')
					if account_name:
						account_row = data_list_account_name.get(account_name)
						data_index_ = account_row['index']
						data[data_index_].update({ branch_key : element[key[0]]})			
					else:
						element.update({ branch_key : element[key[0]]})			
						data.append(element)
	return data

def get_data(companies, root_type, balance_must_be, fiscal_year, filters=None, ignore_closing_entries=False, branch=None):
	accounts, accounts_by_name, parent_children_map = get_account_heads(root_type, companies, filters)

	if not accounts:
		return []

	company_currency = get_company_currency(filters)

	if filters.filter_based_on == "Fiscal Year":
		start_date = fiscal_year.year_start_date if filters.report != "Balance Sheet" else None
		end_date = fiscal_year.year_end_date
	else:
		start_date = filters.period_start_date if filters.report != "Balance Sheet" else None
		end_date = filters.period_end_date

	filters.end_date = end_date

	gl_entries_by_account = {}
	for root in frappe.db.sql(
		"""select lft, rgt from tabAccount
			where root_type=%s and ifnull(parent_account, '') = ''""",
		root_type,
		as_dict=1,
	):
		set_gl_entries_by_account(
			start_date,
			end_date,
			root.lft,
			root.rgt,
			filters,
			gl_entries_by_account,
			accounts_by_name,
			accounts,
			ignore_closing_entries=ignore_closing_entries,
			root_type=root_type,
			branch=branch
		)

	calculate_values(accounts_by_name, gl_entries_by_account, companies, filters, fiscal_year)
	accumulate_values_into_parents(accounts, accounts_by_name, companies)

	out = prepare_data(accounts, start_date, end_date, balance_must_be, companies, company_currency, filters)

	out = filter_out_zero_value_rows(
		out, parent_children_map, show_zero_values=filters.get("show_zero_values")
	)

	if out:
		add_total_row(out, root_type, balance_must_be, companies, company_currency)

	return out


def get_company_currency(filters=None):
	return filters.get("presentation_currency") or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)


def calculate_values(accounts_by_name, gl_entries_by_account, companies, filters, fiscal_year):
	start_date = (
		fiscal_year.year_start_date if filters.filter_based_on == "Fiscal Year" else filters.period_start_date
	)

	for entries in gl_entries_by_account.values():
		for entry in entries:
			if entry.account_number:
				account_name = entry.account_number + " - " + entry.account_name
			else:
				account_name = entry.account_name

			d = accounts_by_name.get(account_name)

			if d:
				debit, credit = 0, 0
				for company in companies:
					# check if posting date is within the period
					if (
						entry.company == company
						or (filters.get("accumulated_in_group_company"))
						and entry.company in companies.get(company)
					):
						parent_company_currency = erpnext.get_company_currency(d.company)
						child_company_currency = erpnext.get_company_currency(entry.company)

						debit, credit = flt(entry.debit), flt(entry.credit)

						if (
							not filters.get("presentation_currency")
							and entry.company != company
							and parent_company_currency != child_company_currency
							and filters.get("accumulated_in_group_company")
						):
							debit = convert(
								debit, parent_company_currency, child_company_currency, filters.end_date
							)
							credit = convert(
								credit, parent_company_currency, child_company_currency, filters.end_date
							)

						d[company] = d.get(company, 0.0) + flt(debit) - flt(credit)

						if entry.posting_date < getdate(start_date):
							d["company_wise_opening_bal"][company] += flt(debit) - flt(credit)

				if entry.posting_date < getdate(start_date):
					d["opening_balance"] = d.get("opening_balance", 0.0) + flt(debit) - flt(credit)


def accumulate_values_into_parents(accounts, accounts_by_name, companies):
	"""accumulate children's values in parent accounts"""
	for d in reversed(accounts):
		if d.parent_account:
			account = d.parent_account_name

			for company in companies:
				accounts_by_name[account][company] = accounts_by_name[account].get(company, 0.0) + d.get(
					company, 0.0
				)

				accounts_by_name[account]["company_wise_opening_bal"][company] += d.get(
					"company_wise_opening_bal", {}
				).get(company, 0.0)

			accounts_by_name[account]["opening_balance"] = accounts_by_name[account].get(
				"opening_balance", 0.0
			) + d.get("opening_balance", 0.0)


def get_account_heads(root_type, companies, filters):
	accounts = get_accounts(root_type, companies)

	if not accounts:
		return None, None, None

	accounts = update_parent_account_names(accounts)

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	return accounts, accounts_by_name, parent_children_map


def update_parent_account_names(accounts):
	"""Update parent_account_name in accounts list.

	parent_name is `name` of parent account which could have other prefix
	of account_number and suffix of company abbr. This function adds key called
	`parent_account_name` which does not have such prefix/suffix.
	"""
	name_to_account_map = {}

	for d in accounts:
		if d.account_number:
			account_key = d.account_number + " - " + d.account_name
		else:
			account_key = d.account_name

		d.account_key = account_key

		name_to_account_map[d.name] = account_key

	for account in accounts:
		if account.parent_account:
			account["parent_account_name"] = name_to_account_map.get(account.parent_account)

	return accounts


def get_companies(filters):
	companies = {}
	all_companies = get_subsidiary_companies(filters.get("company"))
	companies.setdefault(filters.get("company"), all_companies)

	for d in all_companies:
		if d not in companies:
			subsidiary_companies = get_subsidiary_companies(d)
			companies.setdefault(d, subsidiary_companies)

	return all_companies, companies


def get_subsidiary_companies(company):
	lft, rgt = frappe.get_cached_value("Company", company, ["lft", "rgt"])

	return frappe.db.sql_list(
		f"""select name from `tabCompany`
		where lft >= {lft} and rgt <= {rgt} order by lft, rgt"""
	)


def get_accounts(root_type, companies):
	accounts = []

	for company in companies:
		accounts.extend(
			frappe.get_all(
				"Account",
				fields=[
					"name",
					"is_group",
					"company",
					"parent_account",
					"lft",
					"rgt",
					"root_type",
					"report_type",
					"account_name",
					"account_number",
				],
				filters={"company": company, "root_type": root_type},
			)
		)

	return accounts


def prepare_data(accounts, start_date, end_date, balance_must_be, companies, company_currency, filters):
	data = []

	for d in accounts:
		# add to output
		has_value = False
		total = 0
		row = frappe._dict(
			{
				"account_name": (
					f"{_(d.account_number)} - {_(d.account_name)}" if d.account_number else _(d.account_name)
				),
				"account": _(d.name),
				"parent_account": _(d.parent_account),
				"indent": flt(d.indent),
				"year_start_date": start_date,
				"root_type": d.root_type,
				"year_end_date": end_date,
				"currency": filters.presentation_currency,
				"company_wise_opening_bal": d.company_wise_opening_bal,
				"opening_balance": d.get("opening_balance", 0.0) * (1 if balance_must_be == "Debit" else -1),
			}
		)

		for company in companies:
			if d.get(company) and balance_must_be == "Credit":
				# change sign based on Debit or Credit, since calculation is done using (debit - credit)
				d[company] *= -1

			row[company] = flt(d.get(company, 0.0), 3)

			if abs(row[company]) >= 0.005:
				# ignore zero values
				has_value = True
				total += flt(row[company])

		row["has_value"] = has_value
		row["total"] = total

		data.append(row)

	return data


def set_gl_entries_by_account(
	from_date,
	to_date,
	root_lft,
	root_rgt,
	filters,
	gl_entries_by_account,
	accounts_by_name,
	accounts,
	ignore_closing_entries=False,
	root_type=None,
	branch = None
):
	"""Returns a dict like { "account": [gl entries], ... }"""

	company_lft, company_rgt = frappe.get_cached_value("Company", filters.get("company"), ["lft", "rgt"])

	companies = frappe.db.sql(
		""" select name, default_currency from `tabCompany`
		where lft >= %(company_lft)s and rgt <= %(company_rgt)s""",
		{
			"company_lft": company_lft,
			"company_rgt": company_rgt,
		},
		as_dict=1,
	)

	currency_info = frappe._dict(
		{"report_date": to_date, "presentation_currency": filters.get("presentation_currency")}
	)

	for d in companies:
		gle = frappe.qb.DocType("GL Entry")
		account = frappe.qb.DocType("Account")
		query = (
			frappe.qb.from_(gle)
			.inner_join(account)
			.on(account.name == gle.account)
			.select(
				gle.posting_date,
				gle.account,
				gle.debit,
				gle.credit,
				gle.is_opening,
				gle.company,
				gle.fiscal_year,
				gle.debit_in_account_currency,
				gle.credit_in_account_currency,
				gle.account_currency,
				gle.branch,
				account.account_name,
				account.account_number,
			)
			.where(
				(gle.company == d.name)
				& (gle.is_cancelled == 0)
				& (gle.posting_date <= to_date)
				& (account.lft >= root_lft)
				& (account.rgt <= root_rgt)
				& (gle.branch == branch)
			)
			.orderby(gle.account, gle.posting_date)
		)

		if root_type:
			query = query.where(account.root_type == root_type)
		additional_conditions = get_additional_conditions(from_date, ignore_closing_entries, filters, d)
		if additional_conditions:
			query = query.where(Criterion.all(additional_conditions))
		gl_entries = query.run(as_dict=True)

		if filters and filters.get("presentation_currency") != d.default_currency:
			currency_info["company"] = d.name
			currency_info["company_currency"] = d.default_currency
			convert_to_presentation_currency(gl_entries, currency_info)

		for entry in gl_entries:
			if entry.account_number:
				account_name = entry.account_number + " - " + entry.account_name
			else:
				account_name = entry.account_name

			validate_entries(account_name, entry, accounts_by_name, accounts)
			gl_entries_by_account.setdefault(account_name, []).append(entry)

	return gl_entries_by_account


def get_account_details(account):
	return frappe.get_cached_value(
		"Account",
		account,
		[
			"name",
			"report_type",
			"root_type",
			"company",
			"is_group",
			"account_name",
			"account_number",
			"parent_account",
			"lft",
			"rgt",
		],
		as_dict=1,
	)


def validate_entries(key, entry, accounts_by_name, accounts):
	# If an account present in the child company and not in the parent company
	if key not in accounts_by_name:
		args = get_account_details(entry.account)

		if args.parent_account:
			parent_args = get_account_details(args.parent_account)

			args.update(
				{
					"lft": parent_args.lft + 1,
					"rgt": parent_args.rgt - 1,
					"indent": 3,
					"root_type": parent_args.root_type,
					"report_type": parent_args.report_type,
					"parent_account_name": parent_args.account_name,
					"company_wise_opening_bal": defaultdict(float),
				}
			)

		accounts_by_name.setdefault(key, args)

		idx = len(accounts)
		# To identify parent account index
		for index, row in enumerate(accounts):
			if row.parent_account_name == args.parent_account_name:
				idx = index
				break

		accounts.insert(idx + 1, args)


def get_additional_conditions(from_date, ignore_closing_entries, filters, d):
	gle = frappe.qb.DocType("GL Entry")
	additional_conditions = []

	if ignore_closing_entries:
		additional_conditions.append(gle.voucher_type != "Period Closing Voucher")

	if from_date:
		additional_conditions.append(gle.posting_date >= from_date)

	finance_books = []
	finance_books.append("")
	if filter_fb := filters.get("finance_book"):
		finance_books.append(filter_fb)

	if filters.get("include_default_book_entries"):
		if company_fb := frappe.get_cached_value("Company", d.name, "default_finance_book"):
			finance_books.append(company_fb)

		additional_conditions.append((gle.finance_book.isin(finance_books)) | gle.finance_book.isnull())
	else:
		additional_conditions.append((gle.finance_book.isin(finance_books)) | gle.finance_book.isnull())

	return additional_conditions


def add_total_row(out, root_type, balance_must_be, companies, company_currency):
	total_row = {
		"account_name": "'" + _("Total {0} ({1})").format(_(root_type), _(balance_must_be)) + "'",
		"account": "'" + _("Total {0} ({1})").format(_(root_type), _(balance_must_be)) + "'",
		"currency": company_currency,
	}

	for row in out:
		if not row.get("parent_account"):
			for company in companies:
				total_row.setdefault(company, 0.0)
				total_row[company] += row.get(company, 0.0)

			total_row.setdefault("total", 0.0)
			total_row["total"] += flt(row["total"])
			row["total"] = ""

	if "total" in total_row:
		out.append(total_row)

		# blank row after Total
		out.append({})


def filter_accounts(accounts, depth=10):
	parent_children_map = {}
	accounts_by_name = {}
	added_accounts = []

	for d in accounts:
		if d.account_key in added_accounts:
			continue

		added_accounts.append(d.account_key)
		d["company_wise_opening_bal"] = defaultdict(float)
		accounts_by_name[d.account_key] = d

		parent_children_map.setdefault(d.parent_account_name or None, []).append(d)

	filtered_accounts = []

	def add_to_list(parent, level):
		if level < depth:
			children = parent_children_map.get(parent) or []
			sort_accounts(children, is_root=True if parent is None else False)

			for child in children:
				child.indent = level
				filtered_accounts.append(child)
				add_to_list(child.account_key, level + 1)

	add_to_list(None, 0)

	return filtered_accounts, accounts_by_name, parent_children_map

def company_branches(company):
	branches = frappe.get_all("Branch", filters={"company": company}, pluck="name")
	return branches

def calculate_report_summary(report_summary, report_summary_list):
	if not report_summary_list:
		return report_summary

	row_key_value = {row.get("label"): row.get("value") for row in report_summary_list if row.get("label")}
	for element in report_summary:
		value = row_key_value[element.get('label')]
		value += element.get('value')
		element['value'] = value 
	
	return report_summary


def get_account_type_based_gl_data(company, filters=None, branch_val = None):
	cond = ""
	filters = frappe._dict(filters or {})

	if filters.include_default_book_entries:
		company_fb = frappe.get_cached_value("Company", company, "default_finance_book")
		cond = """ AND (finance_book in ({}, {}, '') OR finance_book IS NULL)
			""".format(
			frappe.db.escape(filters.finance_book),
			frappe.db.escape(company_fb),
		)
	else:
		cond = " AND (finance_book in (%s, '') OR finance_book IS NULL)" % (
			frappe.db.escape(cstr(filters.finance_book))
		)

	if filters.get("cost_center"):
		filters.cost_center = get_cost_centers_with_children(filters.cost_center)
		cond += " and cost_center in %(cost_center)s"

	gl_sum = frappe.db.sql_list(
		f"""
		select  sum(credit) - sum(debit)
		from `tabGL Entry`
		where company=%(company)s and posting_date >= %(start_date)s and posting_date <= %(end_date)s
			and voucher_type != 'Period Closing Voucher'
			and branch = "{branch_val}"
			and account in ( SELECT name FROM tabAccount WHERE account_type = %(account_type)s) {cond}
	""",
		filters,
	)

	return gl_sum[0] if gl_sum and gl_sum[0] else 0