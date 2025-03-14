import frappe

from erpnext.accounts.utils import get_fiscal_year
from erpnext.accounts.doctype.budget.budget import (
    get_item_details, get_actions, get_accumulated_monthly_budget,
    get_requested_amount, get_ordered_amount, BudgetError, get_expense_breakup
)
from frappe.utils import flt, get_last_day, fmt_money
from frappe import _

def verify_validate_expense_against_budget(doc):
    gl_entries = doc.get_gl_entries()
    for entry in gl_entries:
        validate_expense_against_budget(entry, expense_amount=flt(entry.debit) - flt(entry.credit))

def validate_expense_against_budget(args, expense_amount=0):
    args = frappe._dict(args)
    if not frappe.get_all("UIS - Allocate Budget", limit=1):
        return

    if args.get("company") and not args.get('fiscal_year'):
        args.fiscal_year = get_fiscal_year(args.get("posting_date"), company=args.get("company"))[0]
    
    frappe.flags.exception_approver_role = frappe.get_cached_value(
        "Company", args.get("company"), "exception_budget_approver_role"
    )

    if not frappe.get_cached_value("UIS - Allocate Budget", {"fiscal_year": args.fiscal_year, "company": args.company}):
        return

    if not args.account:
        args.account = args.get("expense_account")
    
    if not (args.get("account") and args.get("cost_center")) and args.item_code:
        args.cost_center, args.account = get_item_details(args)

    if not args.account:
        return

    # Construct dynamic conditions based on available fields
    condition = ""
    query_params = [args.fiscal_year, args.account]
    
    filters = {"cost_center": "b.cost_center", "project": "b.project", "department": "b.department", "branch": "b.branch"}
    for field, column in filters.items():
        if args.get(field):
            condition += f" AND {column} = %s"
            query_params.append(args.get(field).strip())

    query = f"""
    SELECT
        branch as budget_against, ba.budget_amount,
        b.monthly_distribution,
        IFNULL(b.applicable_on_material_request, 0) AS for_material_request,
        IFNULL(b.applicable_on_purchase_order, 0) AS for_purchase_order,
        IFNULL(b.applicable_on_booking_actual_expenses, 0) AS for_actual_expenses,
        b.action_if_annual_budget_exceeded,
        b.action_if_accumulated_monthly_budget_exceeded,
        b.action_if_annual_budget_exceeded_on_mr,
        b.action_if_accumulated_monthly_budget_exceeded_on_mr,
        b.action_if_annual_budget_exceeded_on_po,
        b.action_if_accumulated_monthly_budget_exceeded_on_po
    FROM `tabUIS - Allocate Budget` b
    INNER JOIN `tabBudget Account` ba ON b.name = ba.parent
    WHERE
        b.fiscal_year = %s
        AND ba.account = %s
        AND b.docstatus = 1
        {condition}
    """

    budget_records = frappe.db.sql(query, tuple(query_params), as_dict=True) # nosec

    if budget_records:
        validate_budget_records(args, budget_records, expense_amount)

def validate_budget_records(args, budget_records, expense_amount):
    for budget in budget_records:
        if flt(budget.budget_amount):
            yearly_action, monthly_action = get_actions(args, budget)
            args["for_material_request"] = budget.for_material_request
            args["for_purchase_order"] = budget.for_purchase_order
            args["for_actual_expenses"] = budget.for_actual_expenses
            args['budget_against_field'] = "branch"
            
            if yearly_action in ("Stop", "Warn"):
                compare_expense_with_budget(
                    args,
                    flt(budget.budget_amount),
                    _("Annual"),
                    yearly_action,
                    budget.budget_against,
                    expense_amount,
                )

            if monthly_action in ["Stop", "Warn"]:
                budget_amount = get_accumulated_monthly_budget(
                    budget.monthly_distribution, args.posting_date, args.fiscal_year, budget.budget_amount
                )

                args["month_end_date"] = get_last_day(args.posting_date)

                compare_expense_with_budget(
                    args,
                    budget_amount,
                    _("Accumulated Monthly"),
                    monthly_action,
                    budget.budget_against,
                    expense_amount,
                )

def compare_expense_with_budget(args, budget_amount, action_for, action, budget_against, amount=0):
    args.actual_expense = get_actual_expense(args)
    args.requested_amount, args.ordered_amount = get_requested_amount(args), get_ordered_amount(args)
    
    total_expense = args.actual_expense + args.ordered_amount
    
    if total_expense > budget_amount:
        error_tense = _("is already") if args.actual_expense > budget_amount else _("will be")
        diff = abs(total_expense - budget_amount)
        currency = frappe.get_cached_value("Company", args.company, "default_currency")
        
        msg = _("{0} Budget for Account {1} against {2} {3} is {4}. It {5} exceed by {6}").format(
            _(action_for),
            frappe.bold(args.account),
            frappe.unscrub(args.budget_against_field),
            frappe.bold(budget_against),
            frappe.bold(fmt_money(budget_amount, currency=currency)),
            error_tense,
            frappe.bold(fmt_money(diff, currency=currency)),
        )
        
        msg += get_expense_breakup(args, currency, budget_against)
        msg += "</ul>"
        
        if frappe.flags.exception_approver_role and frappe.flags.exception_approver_role in frappe.get_roles(
            frappe.session.user
        ):
            action = "Warn"

        if action == "Stop":
            frappe.throw(msg, BudgetError, title=_("Budget Exceeded"))
        else:
            frappe.msgprint(msg, indicator="orange", title=_("Budget Exceeded"))

def get_actual_expense(args):
    budget_against_field = args.get("budget_against_field")
    condition1 = " and gle.posting_date <= %(month_end_date)s" if args.get("month_end_date") else ""
    
    conditions = []
    filters = {"cost_center": "gle.cost_center", "project": "gle.project", "department": "gle.department", "branch": "gle.branch"}
    for field, column in filters.items():
        if args.get(field):
            conditions.append(f"{column} = %({field})s")
    
    condition2 = " AND " + " AND ".join(conditions) if conditions else ""
    
    amount = flt(
        frappe.db.sql(
            f"""
            select sum(gle.debit) - sum(gle.credit)
            from `tabGL Entry` gle
            where
                is_cancelled = 0
                and gle.account=%(account)s
                {condition1}
                and gle.fiscal_year=%(fiscal_year)s
                and gle.company=%(company)s
                and gle.docstatus=1
                {condition2}
            """,
            args,
        )[0][0] or 0
    )
    return amount


def get_remaining_budget(doc, expense_account, branch=None, cost_center=None, project=None, department=None):
    doc = frappe.parse_json(doc)
    fiscal_year = get_fiscal_year(doc.get("posting_date"), company=doc.get("company"))[0]
    company = doc.get("company")
    
    if not fiscal_year or not company:
        return {"error": _("Fiscal Year or Company not set in defaults")}

    filters = {"fiscal_year": fiscal_year, "company": company, "account": expense_account}
    conditions = ""

    if branch:
        conditions += " AND b.branch = %(branch)s"
        filters["branch"] = branch
    if cost_center:
        conditions += " AND b.cost_center = %(cost_center)s"
        filters["cost_center"] = cost_center
    if project:
        conditions += " AND b.project = %(project)s"
        filters["project"] = project
    if department:
        conditions += " AND b.department = %(department)s"
        filters["department"] = department

    budget_data = frappe.db.sql(
        f"""
        SELECT SUM(ba.budget_amount) AS total_budget,
               (SUM(ba.budget_amount) - COALESCE(SUM(gle.debit - gle.credit), 0)) AS remaining_budget
        FROM `tabUIS - Allocate Budget` b
        INNER JOIN `tabBudget Account` ba ON b.name = ba.parent
        LEFT JOIN `tabGL Entry` gle ON gle.account = ba.account
        WHERE b.fiscal_year = %(fiscal_year)s AND ba.account = %(account)s
        AND b.company = %(company)s {conditions}
        """,
        filters,
        as_dict=True,
    )

    return budget_data[0] if budget_data else {"total_budget": 0, "remaining_budget": 0}



@frappe.whitelist()
def fetch_remaining_budget(doc, expense_account, branch=None, cost_center=None, project=None, department=None):
    return get_remaining_budget(doc, expense_account, branch, cost_center, project, department)



