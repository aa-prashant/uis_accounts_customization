# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, cstr, flt, formatdate, getdate
import datetime

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
from erpnext.accounts.report.financial_statements import (
	filter_accounts,
	filter_out_zero_value_rows,
	get_accounting_entries,
)
from erpnext.accounts.report.utils import convert_to_presentation_currency, get_currency
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pypika.terms import ExistsCriterion

value_fields = (
	"opening_debit",
	"opening_credit",
	"debit",
	"credit",
	"closing_debit",
	"closing_credit",
)


def execute(filters=None):
	validate_filters(filters)
	account_budget = get_total_budget(filters)
	companies_column, companies = get_companies(filters)
	data = {}
	for company in companies_column:
		if "UIS Group" == company:
			continue
		filters['company'] = companies_column
		
		data_list = get_data(filters)
		data[company] = data_list
	data = format_data_list(data, account_budget)
	columns = get_columns()
	return columns, data


def validate_filters(filters):
	if not filters.fiscal_year:
		frappe.throw(_("Fiscal Year {0} is required").format(filters.fiscal_year))

	fiscal_year = frappe.get_cached_value(
		"Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
	)
	if not fiscal_year:
		frappe.throw(_("Fiscal Year {0} does not exist").format(filters.fiscal_year))
	else:
		filters.year_start_date = getdate(fiscal_year.year_start_date)
		filters.year_end_date = getdate(fiscal_year.year_end_date)

	if not filters.from_date:
		filters.from_date = filters.year_start_date

	if not filters.to_date:
		filters.to_date = filters.year_end_date

	filters.from_date = getdate(filters.from_date)
	filters.to_date = getdate(filters.to_date)

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))

	if (filters.from_date < filters.year_start_date) or (filters.from_date > filters.year_end_date):
		frappe.msgprint(
			_("From Date should be within the Fiscal Year. Assuming From Date = {0}").format(
				formatdate(filters.year_start_date)
			)
		)

		filters.from_date = filters.year_start_date

	if (filters.to_date < filters.year_start_date) or (filters.to_date > filters.year_end_date):
		frappe.msgprint(
			_("To Date should be within the Fiscal Year. Assuming To Date = {0}").format(
				formatdate(filters.year_end_date)
			)
		)
		filters.to_date = filters.year_end_date


def get_data(filters):
	company = ""
	for company_name in filters.company:
		company += f'"{company_name}",'

	company = company[:-1]
	query = f"select name, account_number, parent_account, account_name, root_type, report_type, lft, rgt from `tabAccount` where company in ({company}) order by lft"
	accounts = frappe.db.sql(
		query,
		as_dict=True,
	)
	company_currency = filters.presentation_currency or erpnext.get_company_currency(filters.company)

	ignore_is_opening = frappe.db.get_single_value(
		"Accounts Settings", "ignore_is_opening_check_for_reporting"
	)

	if not accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	gl_entries_by_account = {}

	opening_balances = get_opening_balances(filters, ignore_is_opening)

	# add filter inside list so that the query in financial_statements.py doesn't break
	if filters.project:
		filters.project = [filters.project]

	set_gl_entries_by_account(
		filters.company,
		filters.from_date,
		filters.to_date,
		filters,
		gl_entries_by_account,
		root_lft=None,
		root_rgt=None,
		ignore_closing_entries=not flt(filters.with_period_closing_entry_for_current_period),
		ignore_opening_entries=True,
	)

	calculate_values(
		accounts,
		gl_entries_by_account,
		opening_balances,
		filters.get("show_net_values"),
		ignore_is_opening=ignore_is_opening,
	)
	accumulate_values_into_parents(accounts, accounts_by_name)

	data = prepare_data(accounts, filters, parent_children_map, company_currency)
	data = filter_out_zero_value_rows(
		data, parent_children_map, show_zero_values=filters.get("show_zero_values")
	)

	return data


def get_opening_balances(filters, ignore_is_opening):
	balance_sheet_opening = get_rootwise_opening_balances(filters, "Balance Sheet", ignore_is_opening)
	pl_opening = get_rootwise_opening_balances(filters, "Profit and Loss", ignore_is_opening)

	balance_sheet_opening.update(pl_opening)
	return balance_sheet_opening


def get_rootwise_opening_balances(filters, report_type, ignore_is_opening):
	gle = []

	last_period_closing_voucher = ""
	ignore_closing_balances = frappe.db.get_single_value(
		"Accounts Settings", "ignore_account_closing_balance"
	)

	if not ignore_closing_balances:
		last_period_closing_voucher = frappe.db.get_all(
			"Period Closing Voucher",
			filters={"docstatus": 1, "company": ['in', filters.company], "period_end_date": ("<", filters.from_date)},
			fields=["period_end_date", "name"],
			order_by="period_end_date desc",
			limit=1,
		)

	accounting_dimensions = get_accounting_dimensions(as_list=False)

	if last_period_closing_voucher:
		gle = get_opening_balance(
			"Account Closing Balance",
			filters,
			report_type,
			accounting_dimensions,
			period_closing_voucher=last_period_closing_voucher[0].name,
			ignore_is_opening=ignore_is_opening,
		)

		# Report getting generate from the mid of a fiscal year
		if getdate(last_period_closing_voucher[0].period_end_date) < getdate(add_days(filters.from_date, -1)):
			start_date = add_days(last_period_closing_voucher[0].period_end_date, 1)
			gle += get_opening_balance(
				"GL Entry",
				filters,
				report_type,
				accounting_dimensions,
				start_date=start_date,
				ignore_is_opening=ignore_is_opening,
			)
	else:
		gle = get_opening_balance(
			"GL Entry", filters, report_type, accounting_dimensions, ignore_is_opening=ignore_is_opening
		)

	opening = frappe._dict()
	for d in gle:
		opening.setdefault(
			d.account,
			{
				"account": d.account,
				"opening_debit": 0.0,
				"opening_credit": 0.0,
			},
		)
		opening[d.account]["opening_debit"] += flt(d.debit)
		opening[d.account]["opening_credit"] += flt(d.credit)

	return opening


def get_opening_balance(
	doctype,
	filters,
	report_type,
	accounting_dimensions,
	period_closing_voucher=None,
	start_date=None,
	ignore_is_opening=0,
):
	closing_balance = frappe.qb.DocType(doctype)
	account = frappe.qb.DocType("Account")

	opening_balance = (
		frappe.qb.from_(closing_balance)
		.select(
			closing_balance.account,
			closing_balance.account_currency,
			Sum(closing_balance.debit).as_("debit"),
			Sum(closing_balance.credit).as_("credit"),
			Sum(closing_balance.debit_in_account_currency).as_("debit_in_account_currency"),
			Sum(closing_balance.credit_in_account_currency).as_("credit_in_account_currency"),
		)
		.where(
			(closing_balance.company.isin( filters.company))
			& (
				closing_balance.account.isin(
					frappe.qb.from_(account).select("name").where(account.report_type == report_type)
				)
			)
		)
		.groupby(closing_balance.account)
	)

	if period_closing_voucher:
		opening_balance = opening_balance.where(
			closing_balance.period_closing_voucher == period_closing_voucher
		)
	else:
		if start_date:
			opening_balance = opening_balance.where(
				(closing_balance.posting_date >= start_date)
				& (closing_balance.posting_date < filters.from_date)
			)

			if not ignore_is_opening:
				opening_balance = opening_balance.where(closing_balance.is_opening == "No")
		else:
			if not ignore_is_opening:
				opening_balance = opening_balance.where(
					(closing_balance.posting_date < filters.from_date) | (closing_balance.is_opening == "Yes")
				)
			else:
				opening_balance = opening_balance.where(closing_balance.posting_date < filters.from_date)

	if doctype == "GL Entry":
		opening_balance = opening_balance.where(closing_balance.is_cancelled == 0)

	if (
		not filters.show_unclosed_fy_pl_balances
		and report_type == "Profit and Loss"
		and doctype == "GL Entry"
	):
		opening_balance = opening_balance.where(closing_balance.posting_date >= filters.year_start_date)

	if not flt(filters.with_period_closing_entry_for_opening):
		if doctype == "Account Closing Balance":
			opening_balance = opening_balance.where(closing_balance.is_period_closing_voucher_entry == 0)
		else:
			opening_balance = opening_balance.where(closing_balance.voucher_type != "Period Closing Voucher")

	if filters.cost_center:
		lft, rgt = frappe.db.get_value("Cost Center", filters.cost_center, ["lft", "rgt"])
		cost_center = frappe.qb.DocType("Cost Center")
		opening_balance = opening_balance.where(
			closing_balance.cost_center.isin(
				frappe.qb.from_(cost_center)
				.select("name")
				.where((cost_center.lft >= lft) & (cost_center.rgt <= rgt))
			)
		)

	if filters.project:
		opening_balance = opening_balance.where(closing_balance.project == filters.project)

	if filters.get("include_default_book_entries"):
		company_fb = frappe.get_cached_value("Company", filters.company, "default_finance_book")

		if filters.finance_book and company_fb and cstr(filters.finance_book) != cstr(company_fb):
			frappe.throw(_("To use a different finance book, please uncheck 'Include Default FB Entries'"))

		opening_balance = opening_balance.where(
			(closing_balance.finance_book.isin([cstr(filters.finance_book), cstr(company_fb), ""]))
			| (closing_balance.finance_book.isnull())
		)
	else:
		opening_balance = opening_balance.where(
			(closing_balance.finance_book.isin([cstr(filters.finance_book), ""]))
			| (closing_balance.finance_book.isnull())
		)

	if accounting_dimensions:
		for dimension in accounting_dimensions:
			if filters.get(dimension.fieldname):
				if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
					filters[dimension.fieldname] = get_dimension_with_children(
						dimension.document_type, filters.get(dimension.fieldname)
					)
					opening_balance = opening_balance.where(
						closing_balance[dimension.fieldname].isin(filters[dimension.fieldname])
					)
				else:
					opening_balance = opening_balance.where(
						closing_balance[dimension.fieldname].isin(filters[dimension.fieldname])
					)

	gle = opening_balance.run(as_dict=1)

	if filters and filters.get("presentation_currency"):
		convert_to_presentation_currency(gle, get_currency(filters))

	return gle


def calculate_values(accounts, gl_entries_by_account, opening_balances, show_net_values, ignore_is_opening=0):
	init = {
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0,
	}

	for d in accounts:
		d.update(init.copy())

		# add opening
		d["opening_debit"] = opening_balances.get(d.name, {}).get("opening_debit", 0)
		d["opening_credit"] = opening_balances.get(d.name, {}).get("opening_credit", 0)

		for entry in gl_entries_by_account.get(d.name, []):
			if cstr(entry.is_opening) != "Yes" or ignore_is_opening:
				d["debit"] += flt(entry.debit)
				d["credit"] += flt(entry.credit)

		d["closing_debit"] = d["opening_debit"] + d["debit"]
		d["closing_credit"] = d["opening_credit"] + d["credit"]

		if show_net_values:
			prepare_opening_closing(d)


def calculate_total_row(accounts, company_currency):
	total_row = {
		"account": "'" + _("Total") + "'",
		"account_name": "'" + _("Total") + "'",
		"warn_if_negative": True,
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0,
		"parent_account": None,
		"indent": 0,
		"has_value": True,
		"currency": company_currency,
	}

	for d in accounts:
		if not d.parent_account:
			for field in value_fields:
				total_row[field] += d[field]

	return total_row


def accumulate_values_into_parents(accounts, accounts_by_name):
	for d in reversed(accounts):
		if d.parent_account:
			for key in value_fields:
				accounts_by_name[d.parent_account][key] += d[key]


def prepare_data(accounts, filters, parent_children_map, company_currency):
	data = []

	for d in accounts:
		# Prepare opening closing for group account
		if parent_children_map.get(d.account) and filters.get("show_net_values"):
			prepare_opening_closing(d)

		has_value = False
		row = {
			"account": d.name,
			"parent_account": d.parent_account,
			"indent": d.indent,
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"currency": company_currency,
			"account_name": (
				f"{d.account_number} - {d.account_name}" if d.account_number else d.account_name
			),
		}

		for key in value_fields:
			row[key] = flt(d.get(key, 0.0), 3)

			if abs(row[key]) >= 0.005:
				# ignore zero values
				has_value = True

		row["has_value"] = has_value
		data.append(row)

	total_row = calculate_total_row(accounts, company_currency)
	data.extend([{}, total_row])

	return data


def get_columns():
	return [
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
			"fieldname": "opening_debit",
			"label": _("Opening (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "opening_credit",
			"label": _("Opening (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "opening_budget",
			"label": _("Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "total_estimate_monthly",
			"label": _("Total Estimation Monthly"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_debit",
			"label": _("Closing (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_credit",
			"label": _("Closing (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "year_till_date_budget",
			"label": _("Year to Date Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},

	]


def prepare_opening_closing(row):
	dr_or_cr = "debit" if row["root_type"] in ["Asset", "Equity", "Expense"] else "credit"
	reverse_dr_or_cr = "credit" if dr_or_cr == "debit" else "debit"

	for col_type in ["opening", "closing"]:
		valid_col = col_type + "_" + dr_or_cr
		reverse_col = col_type + "_" + reverse_dr_or_cr
		row[valid_col] -= row[reverse_col]
		if row[valid_col] < 0:
			row[reverse_col] = abs(row[valid_col])
			row[valid_col] = 0.0
		else:
			row[reverse_col] = 0.0


def get_total_budget(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate total budget based on given filters.
    
    Args:
        filters: Dictionary containing fiscal_year, company, branch, from_date, to_date
    
    Returns:
        Dictionary mapping accounts to their budget details
    """
    budget_records = _get_budget_records(filters)
    if not budget_records:
        return {}

    fiscal_year_details = None
    account_budgets = {}
    
    for budget in budget_records:
        # Fetch fiscal year details only once
        if fiscal_year_details is None:
            fiscal_year_details = _get_fiscal_year_details(budget.fiscal_year)
        
        month_ranges = {
            'fy_start': fiscal_year_details.year_start_date.month,
            'fy_end': fiscal_year_details.year_end_date.month,
            'from_month': filters['from_date'].month,
            'to_month': filters['to_date'].month
        }
        
        accounts = _get_budget_accounts(budget.name)
        
        if budget.monthly_distribution:
            distribution_data = _get_monthly_distribution(budget.monthly_distribution)
            budget_factors = _calculate_budget_factors(
                distribution_data, 
                month_ranges['from_month'],
                month_ranges['to_month'],
                month_ranges['fy_start'],
                month_ranges['fy_end']
            )
            
            account_budgets.update(
                _calculate_accounts_with_distribution(
                    accounts, 
                    budget_factors,
                    is_distribution_exists=True
                )
            )
        else:
            account_budgets.update(
                _calculate_accounts_with_distribution(
                    accounts, 
                    (0, 0, 0),
                    is_distribution_exists=False
                )
            )
    
    return account_budgets

def _get_budget_records(filters: Dict[str, Any]) -> List[Any]:
    """Fetch budget records based on filters."""
    budget_filter = {
        "fiscal_year": filters.get("fiscal_year"),
        "company": filters.get('company'),
        "branch": ["in", filters.get("branch")],
        "docstatus": 1,
    }
    
    return frappe.get_all(
        "Budget",
        filters=budget_filter,
        fields=["name", "monthly_distribution", "fiscal_year"]
    )

def _get_fiscal_year_details(fiscal_year: str) -> Any:
    """Fetch fiscal year start and end dates."""
    return frappe.get_value(
        "Fiscal Year",
        fiscal_year,
        ["year_start_date", "year_end_date"],
        as_dict=True
    )

def _get_budget_accounts(budget_name: str) -> List[Any]:
    """Fetch budget accounts for a given budget."""
    return frappe.get_all(
        "Budget Account",
        {"parent": budget_name},
        ["account", "budget_amount"]
    )

def _get_monthly_distribution(distribution_name: str) -> Dict[int, Tuple[Any, int]]:
    """
    Get monthly distribution percentages.
    Returns a dictionary mapping month numbers to (distribution_record, index) tuples.
    """
    distributions = frappe.get_all(
        "Monthly Distribution Percentage",
        {"parent": distribution_name},
        ["*"],
        order_by="idx ASC"
    )
    
    return {
        datetime.strptime(dist.month, "%B").month: (dist, dist.idx - 1)
        for dist in distributions
    }

def _calculate_budget_factors(
    monthly_distribution: Dict[int, Tuple[Any, int]],
    from_month: int,
    to_month: int,
    fy_start_month: int,
    fy_end_month: int
) -> Tuple[float, float, float]:
    """
    Calculate budget distribution factors.
    Returns (total_percentage, total_estimate_monthly, year_to_budget)
    """
    def sum_percentages(start: int, end: int) -> float:
        return sum(
            monthly_distribution[month][0].percentage_allocation
            for month in range(start, end + 1)
            if month in monthly_distribution
        )
    
    total_percentage = (
        0 if fy_start_month == from_month
        else sum_percentages(fy_start_month, from_month - 1)
    )
    
    total_estimate_monthly = sum_percentages(from_month, to_month)
    year_to_budget = sum_percentages(fy_start_month, to_month)
    
    return total_percentage, total_estimate_monthly, year_to_budget
def _parse_account_name(account_string: str) -> str:
    """
    Extract and clean account name from account string.
    
    Args:
        account_string: Full account string with hyphen-separated parts
        
    Returns:
        Cleaned account name from second part if available, otherwise first part
    """
    try:
        parts = account_string.split("-")[:-1]
        return (parts[1] if len(parts) > 1 else parts[0]).strip()
    except (IndexError, AttributeError):
        return account_string

def _calculate_budget_values(
    budget_amount: float,
    budget_factors: Tuple[float, float, float],
    is_distribution_exists: bool
) -> Dict[str, float]:
    """
    Calculate budget values based on distribution factors.
    
    Args:
        budget_amount: Base budget amount
        budget_factors: Distribution percentage factors
        is_distribution_exists: Whether to apply distribution
        
    Returns:
        Dictionary of calculated budget values
    """
    amount = float(budget_amount or 0)
    
    if not is_distribution_exists:
        return {
            'opening_budget': amount,
            'total_estimate_monthly': amount,
            'year_till_date_budget': amount
        }
        
    total_percentage, total_estimate_monthly, year_to_budget = budget_factors
    return {
        'opening_budget': amount * total_percentage / 100,
        'total_estimate_monthly': amount * total_estimate_monthly / 100,
        'year_till_date_budget': amount * year_to_budget / 100
    }

def _calculate_accounts_with_distribution(
    accounts: List[Any],
    budget_factors: Tuple[float, float, float],
    is_distribution_exists: bool = True
) -> Dict[str, Any]:
    """
    Calculate account budgets with distribution factors applied.
    
    Args:
        accounts: List of account records
        budget_factors: Tuple of (total_percentage, total_estimate_monthly, year_to_budget)
        is_distribution_exists: Boolean indicating if monthly distribution exists
        
    Returns:
        Dictionary mapping account names to their budget details
    """
    account_key = {}
    
    for account in accounts:
        # Parse account name once
        account_name = _parse_account_name(account.account)
        
        # Calculate budget values
        budget_values = _calculate_budget_values(
            account.budget_amount,
            budget_factors,
            is_distribution_exists
        )
        
        # Update account with new values
        account.update(budget_values)
        
        # Store in dictionary using processed account name as key
        account_key[account_name] = account
    
    return account_key


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

def format_data_list(data_list, budget_list):
	data_dict = []
	key_dict = {}
	
	for key in data_list:
		data = data_list[key]
		for index,element in enumerate(data):
			if not element:
				data_dict.append(element)
				continue
			account_name = element.get('account_name').split("-")[-1].strip()
			if account_name not in key_dict:
				key_dict[account_name] = index
				if account_name in budget_list:
					element.update(budget_list[account_name])

			data_dict.append(element)
	return data_dict



def set_gl_entries_by_account(
	company,
	from_date,
	to_date,
	filters,
	gl_entries_by_account,
	root_lft=None,
	root_rgt=None,
	root_type=None,
	ignore_closing_entries=False,
	ignore_opening_entries=False,
):
	"""Returns a dict like { "account": [gl entries], ... }"""
	gl_entries = []

	# For balance sheet
	ignore_closing_balances = frappe.db.get_single_value(
		"Accounts Settings", "ignore_account_closing_balance"
	)
	if not from_date and not ignore_closing_balances:
		last_period_closing_voucher = frappe.db.get_all(
			"Period Closing Voucher",
			filters={
				"docstatus": 1,
				"company": ["in", [[filters.company]]],
				"period_end_date": ("<", filters["period_start_date"]),
			},
			fields=["period_end_date", "name"],
			order_by="period_end_date desc",
			limit=1,
		)
		if last_period_closing_voucher:
			gl_entries += get_accounting_entries(
				"Account Closing Balance",
				from_date,
				to_date,
				filters,
				root_lft,
				root_rgt,
				root_type,
				ignore_closing_entries,
				last_period_closing_voucher[0].name,
			)
			from_date = add_days(last_period_closing_voucher[0].period_end_date, 1)
			ignore_opening_entries = True

	gl_entries += get_accounting_entries(
		"GL Entry",
		from_date,
		to_date,
		filters,
		root_lft,
		root_rgt,
		root_type,
		ignore_closing_entries,
		ignore_opening_entries=ignore_opening_entries,
	)

	if filters and filters.get("presentation_currency"):
		convert_to_presentation_currency(gl_entries, get_currency(filters))

	for entry in gl_entries:
		gl_entries_by_account.setdefault(entry.account, []).append(entry)

	return gl_entries_by_account


def get_accounting_entries(
	doctype,
	from_date,
	to_date,
	filters,
	root_lft=None,
	root_rgt=None,
	root_type=None,
	ignore_closing_entries=None,
	period_closing_voucher=None,
	ignore_opening_entries=False,
):
	gl_entry = frappe.qb.DocType(doctype)
	query = (
		frappe.qb.from_(gl_entry)
		.select(
			gl_entry.account,
			gl_entry.debit,
			gl_entry.credit,
			gl_entry.debit_in_account_currency,
			gl_entry.credit_in_account_currency,
			gl_entry.account_currency,
		)
		.where(gl_entry.company == filters.company)
	)

	ignore_is_opening = frappe.db.get_single_value(
		"Accounts Settings", "ignore_is_opening_check_for_reporting"
	)

	if doctype == "GL Entry":
		query = query.select(gl_entry.posting_date, gl_entry.is_opening, gl_entry.fiscal_year)
		query = query.where(gl_entry.is_cancelled == 0)
		query = query.where(gl_entry.posting_date <= to_date)

		if ignore_opening_entries and not ignore_is_opening:
			query = query.where(gl_entry.is_opening == "No")
	else:
		query = query.select(gl_entry.closing_date.as_("posting_date"))
		query = query.where(gl_entry.period_closing_voucher == period_closing_voucher)

	query = apply_additional_conditions(doctype, query, from_date, ignore_closing_entries, filters)

	if (root_lft and root_rgt) or root_type:
		account_filter_query = get_account_filter_query(root_lft, root_rgt, root_type, gl_entry)
		query = query.where(ExistsCriterion(account_filter_query))

	from frappe.desk.reportview import build_match_conditions

	query, params = query.walk()
	match_conditions = build_match_conditions(doctype)

	if match_conditions:
		query += "and" + match_conditions

	return frappe.db.sql(query, params, as_dict=True)

def apply_additional_conditions(doctype, query, from_date, ignore_closing_entries, filters):
	gl_entry = frappe.qb.DocType(doctype)
	accounting_dimensions = get_accounting_dimensions(as_list=False)

	if ignore_closing_entries:
		if doctype == "GL Entry":
			query = query.where(gl_entry.voucher_type != "Period Closing Voucher")
		else:
			query = query.where(gl_entry.is_period_closing_voucher_entry == 0)

	if from_date and doctype == "GL Entry":
		query = query.where(gl_entry.posting_date >= from_date)

	if filters:
		if filters.get("project"):
			if not isinstance(filters.get("project"), list):
				filters.project = frappe.parse_json(filters.get("project"))

			query = query.where(gl_entry.project.isin(filters.project))

		if filters.get("cost_center"):
			filters.cost_center = get_cost_centers_with_children(filters.cost_center)
			query = query.where(gl_entry.cost_center.isin(filters.cost_center))

		if filters.get("include_default_book_entries"):
			company_fb = frappe.get_cached_value("Company", filters.company, "default_finance_book")

			if filters.finance_book and company_fb and cstr(filters.finance_book) != cstr(company_fb):
				frappe.throw(
					_("To use a different finance book, please uncheck 'Include Default FB Entries'")
				)

			query = query.where(
				(gl_entry.finance_book.isin([cstr(filters.finance_book), cstr(company_fb), ""]))
				| (gl_entry.finance_book.isnull())
			)
		else:
			query = query.where(
				(gl_entry.finance_book.isin([cstr(filters.finance_book), ""]))
				| (gl_entry.finance_book.isnull())
			)

	if accounting_dimensions:
		for dimension in accounting_dimensions:
			if filters.get(dimension.fieldname):
				if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
					filters[dimension.fieldname] = get_dimension_with_children(
						dimension.document_type, filters.get(dimension.fieldname)
					)

				query = query.where(gl_entry[dimension.fieldname].isin(filters[dimension.fieldname]))

	return query

def get_cost_centers_with_children(cost_centers):
	if not isinstance(cost_centers, list):
		cost_centers = [d.strip() for d in cost_centers.strip().split(",") if d]

	all_cost_centers = []
	for d in cost_centers:
		if frappe.db.exists("Cost Center", d):
			lft, rgt = frappe.db.get_value("Cost Center", d, ["lft", "rgt"])
			children = frappe.get_all("Cost Center", filters={"lft": [">=", lft], "rgt": ["<=", rgt]})
			all_cost_centers += [c.name for c in children]
		else:
			frappe.throw(_("Cost Center: {0} does not exist").format(d))

	return list(set(all_cost_centers))


def get_account_filter_query(root_lft, root_rgt, root_type, gl_entry):
	acc = frappe.qb.DocType("Account")
	exists_query = (
		frappe.qb.from_(acc).select(acc.name).where(acc.name == gl_entry.account).where(acc.is_group == 0)
	)
	if root_lft and root_rgt:
		exists_query = exists_query.where(acc.lft >= root_lft).where(acc.rgt <= root_rgt)

	if root_type:
		exists_query = exists_query.where(acc.root_type == root_type)

	return exists_query
