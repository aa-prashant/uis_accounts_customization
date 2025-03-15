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
from erpnext.accounts.utils import get_fiscal_year

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
		data = balance_sheet_data_format(data)
	elif filters.get("report") == "Profit and Loss Statement":
		budget_dict, data, message, chart, report_summary = get_profit_loss_data(fiscal_year, companies, columns, filters)
		data = pnl_formatted_report(data, budget_dict)
		is_pnl = True
		
	else:
		data, report_summary = get_cash_flow_data(fiscal_year, companies, filters)
	
	columns = get_columns_branch_wise(companies_column, filters, is_pnl)
	
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
	budget_dict = {}
	for key in companies:
		for company in companies[key]:
			if company in company_fetched_list:
				continue
			company_fetched_list.append(company)
			branches = company_branches(company)
			
			for branch in branches:
				key = (company, branch)
				budget_dict.update(get_account_budget(company,branch, filters))

				data, message, chart, report_summary = get_profit_loss_data_branch_wise(fiscal_year, companies, columns, filters, branch)
				data_list.append({key:data})
	return budget_dict, data_list, message, chart, report_summary

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
					"fieldname": branch,
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
						"fieldname": f"bug_{branch}_{company}",
						"label": f"Budget Allocated - {branch} - ({currency})",
						"fieldtype": "Currency",
						"options": "currency",
						"width": 150,
						"apply_currency_formatter": apply_currency_formatter,
						"company_name": company,
					}
				)

	return columns

def balance_sheet_data_format(data_list):
# Create a dictionary to store consolidated data by account
    consolidated_data = {}
    branches = []
    
    # First pass: extract all branches and account names
    for branch_data in data_list:
        for (company, branch), accounts in branch_data.items():
            if branch not in branches:
                branches.append(branch)
            
            for account in accounts:
                if not isinstance(account, dict) or 'account_name' not in account:
                    continue
                    
                account_name = account['account_name']
                if account_name not in consolidated_data:
                    consolidated_data[account_name] = {
                        'account_name': account_name,
                        'account': account.get('account', ''),
                        'parent_account': account.get('parent_account', ''),
                        'indent': account.get('indent', 0),
                        'root_type': account.get('root_type', ''),
                        'branches': {},
						'currency' : account.get('currency')
                    }
    
    # Second pass: populate branch-specific values
    for branch_data in data_list:
        for (company, branch), accounts in branch_data.items():
            for account in accounts:
                if not isinstance(account, dict) or 'account_name' not in account:
                    continue
                    
                account_name = account['account_name']
                if account_name in consolidated_data:
                    if company in account:
                        consolidated_data[account_name]['branches'][branch] = account[company]
    
    # Group accounts by root_type
    assets = []
    liabilities = []
    equity = []
    other = []
    
    # Prepare report data grouped by root_type
    for account_name, account_data in consolidated_data.items():
        row = {
            'account_name': account_name,
            'account': account_data['account'],
            'parent_account': account_data['parent_account'],
            'indent': account_data['indent'],
            'root_type': account_data['root_type'],
			'currency' : account.get('currency')
        }
        
        # Add branch-specific columns
        for branch in branches:
            row[branch] = account_data['branches'].get(branch, 0)
        
        # Calculate total for the row across all branches
        row['total'] = sum(account_data['branches'].values())
        
        # Sort into appropriate category
        root_type = account_data['root_type'].lower() if account_data['root_type'] else ''
        if root_type == 'asset':
            assets.append(row)
        elif root_type == 'liability':
            liabilities.append(row)
        elif root_type == 'equity':
            equity.append(row)
        else:
            other.append(row)
    
    # Sort each category separately by indent and account name
    for category in [assets, liabilities, equity, other]:
        category.sort(key=lambda x: (x.get('indent', 0), x.get('account_name', '')))
    
    # Combine results with separator rows
    result = []
    
    # Add assets section
    result.extend(assets)
    
    # Add separator row after assets
    if assets and (liabilities or equity or other):
        result.append(create_separator_row(branches))
    
    # Add liabilities section
    result.extend(liabilities)
    
    # Add separator row after liabilities
    if liabilities and (equity or other):
        result.append(create_separator_row(branches))
    
    # Add equity section
    result.extend(equity)
    
    # Add separator row after equity if there are other accounts
    if equity and other:
        result.append(create_separator_row(branches))
    
    # Add other accounts if any
    result.extend(other)
    
    return result

# Helper function to create a separator row
def create_separator_row(branches):
    separator = {
        'account_name': '',
        'account': '',
        'parent_account': '',
        'indent': 0,
        'root_type': '',
        'is_separator': True  # Flag to identify separator rows
    }
    
    # Add empty values for branch columns
    for branch in branches:
        separator[branch] = ''
    
    separator['total'] = ''
    
    return separator

def pnl_formatted_report(data, budget_dict):
    """
    Format profit and loss report data with proper account hierarchy and indentation.
    Maps child accounts to parent accounts and ensures budget values are shown even when there are no entries.
    """
    formatted_data = []
    account_map = {}  # To keep track of accounts by name for easy lookup
    
    # First pass: Get all accounts from data
    for company_branch_data in data:
        for (company, branch), accounts in company_branch_data.items():
            # Process each account
            for account in accounts:
                if not account or 'account_name' not in account:
                    continue
                
                account_name = account.get('account_name')
                
                # Find if this account already exists in formatted_data
                if account_name in account_map:
                    existing_row = account_map[account_name]
                    # Update existing row with this branch's data
                    existing_row[f"{branch}"] = account.get(company, 0)
                    if 'total' in account:
                        existing_row['total'] = account.get('total', 0)
                else:
                    # Create new row for this account
                    new_row = {
                        'account_name': account_name,
                        'account': account.get('account'),
                        'parent_account': account.get('parent_account'),
                        'currency': account.get('currency'),
                        f"{branch}": account.get(company, 0),
                    }
                    if 'total' in account:
                        new_row['total'] = account.get('total', 0)
                    
                    # Use the provided indent if available
                    new_row['indent'] = account.get('indent', 0)
                    
                    formatted_data.append(new_row)
                    account_map[account_name] = new_row
    
    # Second pass: Add budget data, even for accounts that might not have entries
    for (company, branch), budget_accounts in budget_dict.items():
        budget_key = f"bug_{branch}_{company}"
        
        for account_name, budget_amount in budget_accounts.items():
            # If account exists in our formatted data, add budget
            if account_name in account_map:
                account_map[account_name][budget_key] = budget_amount
            else:
                # Try to find parent account info from Frappe DB
                account_info = get_account_info(account_name, company)
                indent = 0
                
                if account_info:
                    indent = account_info.get('indent', 0)
                    
                # Create a new row for budget accounts that don't have entries
                new_row = {
                    'account_name': account_name,
                    'account': account_name,  # Using account_name as fallback
                    'indent': indent,  # Use indent from account_info if available
                    f"{branch}": 0,  # Zero for the branch as no actual entries
                    budget_key: budget_amount  # Add budget amount
                }
                formatted_data.append(new_row)
                account_map[account_name] = new_row
    
    # Important: Preserve the original indentation from the input data
    # If we need to recalculate indentation based on hierarchy, use the following:
    # formatted_data = apply_indentation(formatted_data)
    
    return formatted_data

def get_account_info(account_name, company):
    """
    Get account information from Frappe DB.
    This is a placeholder - in actual implementation, you would query the database.
    
    Example implementation:
    return frappe.db.get_value("Account", 
							{"account_name": account_name, "company": company},
							["parent_account", "is_group", "indent"], 
							as_dict=True)
    """
    # Placeholder implementation
    return None

def apply_indentation(accounts_data):
    """
    Apply indentation based on parent-child relationships.
    This function should be used if the original data doesn't have proper indentation.
    """
    # Create a map of parent to children
    parent_map = {}
    for account in accounts_data:
        parent = account.get('parent_account')
        if parent:
            if parent not in parent_map:
                parent_map[parent] = []
            parent_map[parent].append(account)
    
    # Find root accounts (no parent or parent not in our dataset)
    root_accounts = [account for account in accounts_data 
                    if not account.get('parent_account') or 
                    account.get('parent_account') not in parent_map]
    
    # Apply indentation recursively
    result = []
    for root in root_accounts:
        result.append(root)
        root['indent'] = 0
        apply_indent_recursive(root, parent_map, result, 1)
    
    return result

def apply_indent_recursive(parent, parent_map, result, indent_level):
    """Helper function for recursive indentation"""
    parent_name = parent.get('account_name')
    if parent_name in parent_map:
        for child in parent_map[parent_name]:
            child['indent'] = indent_level
            result.append(child)
            apply_indent_recursive(child, parent_map, result, indent_level + 1)

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

def get_account_budget(company, branch, filters):
    budget_filter = {
        "company": company,
        "branch": branch,
        "fiscal_year": filters.get("from_fiscal_year"),
        "docstatus": 1
    }
    
    account_with_budget_amount_branch_wise = {}
    
    # Get budget details
    budget_dict = frappe.db.get_value(
        "UIS - Budget", 
        budget_filter, 
        ['name', 'monthly_distribution'], 
        as_dict=True
    )
    
    if not budget_dict:
        return {}
    
    # Get account budget amounts
    account_with_budget_amount = frappe.db.get_values(
        "Budget Account", 
        {'parent': budget_dict.get("name")}, 
        ['account', "budget_amount"], 
        as_dict=True
    )
    
    # Get monthly distribution percentages
    monthly_distribution_dict = frappe.db.get_values(
        "Monthly Distribution Percentage",
        {'parent': budget_dict.get("monthly_distribution")},
        ['month', "percentage_allocation"],
        as_dict=True
    )
    
    # Format monthly distribution according to filter period 
    # (now returns total percentage for the period)
    monthly_percentage = round(_format_monthly_distribution_dict(monthly_distribution_dict, filters), 2)
    
    # Create branch-wise account budget dictionary
    key = (company, branch)
    account_with_budget_amount_branch_wise[key] = {}
    
    for account in account_with_budget_amount:
        account_name = _get_account_name(account)
        if account_name:
            if monthly_percentage:
                allocated_budget_amount = (account.get("budget_amount", 0) * monthly_percentage) / 100
            else:
                allocated_budget_amount = account.get("budget_amount", 0)
                
            account_with_budget_amount_branch_wise[key][account_name] = allocated_budget_amount
    
    return account_with_budget_amount_branch_wise

def _get_account_name(account):
    """Extract non-numeric part of the account name"""
    account_parts = account.get("account", "").split("-")
    
    for part in account_parts:
        part = part.strip()
        if part and not part.isnumeric():
            return part
    
    return ""

def _format_monthly_distribution_dict(monthly_distribution_dict, filters):
    """
    Format monthly distribution percentages for the given filter period
    Returns total percentage allocation for months in the filter period
    """
    if not monthly_distribution_dict:
        return 0
    
    # Get start and end dates from filters
    start_date = filters.get("period_start_date")
    end_date = filters.get("period_end_date")
    
    if not start_date or not end_date:
        return sum(item.get("percentage_allocation", 0) for item in monthly_distribution_dict)
    
    # Convert string dates to datetime objects
    from datetime import datetime
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return sum(item.get("percentage_allocation", 0) for item in monthly_distribution_dict)
    
    # Month names list for index lookup
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    # Filter months that fall within the date range
    start_month_idx = start_date.month - 1  # 0-indexed
    end_month_idx = end_date.month - 1      # 0-indexed
    
    # Calculate total percentage for months in range
    total_percentage = 0
    for item in monthly_distribution_dict:
        month = item.get("month")
        if not month:
            continue
            
        # Find month index (0-indexed)
        try:
            month_idx = month_names.index(month)
        except ValueError:
            continue
            
        # Check if month is in the filtered range
        if start_month_idx <= month_idx <= end_month_idx:
            total_percentage += item.get("percentage_allocation", 0)
    
    return total_percentage