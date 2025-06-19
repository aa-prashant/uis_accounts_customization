import frappe
from frappe.utils import getdate
import requests

@frappe.whitelist()
def get_allocated_amount(doc = None, selected_doc=None):
    doc = frappe._dict(frappe.parse_json(doc)) if type(doc) == str else doc
    selected_doc = frappe._dict(frappe.parse_json(selected_doc))  if type(selected_doc) == str else selected_doc
    
    if not selected_doc.item_code :
        return
    
    item_type = get_item_type(selected_doc.item_code)
    if item_type:
        return get_allocated_amount_for_asset(doc, selected_doc)
    
    return get_allocated_amount_for_gl(doc, selected_doc)


def get_allocated_amount_for_asset(doc, selected_doc):

    if not selected_doc.get("item_code"):
        return 0
    
    branch = selected_doc.get("branch") or doc.get("branch")

    if not branch:
        frappe.throw("Branch cannot be empty")

    allocated_budget = get_allocated_budget(doc, selected_doc, branch)
    pi_item_amount = get_used_budget(doc, selected_doc, branch)
    
    return allocated_budget - pi_item_amount

@frappe.whitelist()
def get_fiscal_year(doc):
    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": ["<=", doc.posting_date], "year_end_date": [">=", doc.posting_date]},
        pluck="name"
    )

    return next(
        (fy for fy in fiscal_years if frappe.db.exists("Fiscal Year Company", {"parent": fy, "company": doc.company})),
        None
    )

def get_allocated_budget(doc, selected_doc, branch):
    fiscal_year = get_fiscal_year(doc)
    if not fiscal_year:
        return 0
    
    budget_name = frappe.get_value(
        "Allocate Budget for Asset",
        {"fiscal_year": fiscal_year, "branch": branch, "company": doc.company, "docstatus": 1},
        "name"
    )
    
    if not budget_name:
        return 0

    allocated_budget = frappe.get_value(
        "Budget Item",
        {"parent": budget_name, "item_code": selected_doc.item_code},
        "budget_amount"
    )

    return allocated_budget or 0

def get_used_budget(doc, selected_doc, branch):
    fiscal_year = get_fiscal_year(doc)
    if not fiscal_year:
        return 0
    filters = {
                "item_code" : selected_doc.item_code, 
                "docstatus" : 1,
                "branch" : selected_doc.branch
            }
    pi_item = frappe.db.get_values("Purchase Invoice Item", filters , ["parent", "amount"], as_dict = True)
    used_amount = 0
    for item in pi_item:
        pi_parent_obj = frappe.get_value("Purchase Invoice", item.parent, ["posting_date", "company", "branch"], as_dict=True)

        if doc.company != pi_parent_obj.company and branch != pi_parent_obj.branch:
            continue
        item_parent_fy_year = get_fiscal_year(frappe._dict({"posting_date" : pi_parent_obj.get('posting_date'), "company":pi_parent_obj.company}))
        if fiscal_year == item_parent_fy_year:
            used_amount +=item.amount
    return used_amount

def get_item_type(item_code):
    item_type = frappe.db.get_value("Item", item_code, "is_fixed_asset")
    return item_type

def get_allocated_amount_for_gl(doc, selected_doc):
    if not selected_doc.get("item_code"):
        return 0
    
    branch = selected_doc.get("branch") or doc.get("branch")

    if not branch:
        frappe.throw("Branch cannot be empty")

    fiscal_year = get_fiscal_year(doc)
    if not fiscal_year:
        return 0
    
    budget_name = frappe.get_value(
        "Budget",
        {"fiscal_year": fiscal_year, "branch": branch, "company": doc.company, "docstatus": 1},
        "name"
    )
    
    if not budget_name:
        return 0

    allocated_budget = frappe.get_value(
        "Budget Item",
        {"parent": budget_name, "item_code": selected_doc.item_code},
        "budget_amount"
    )

    return allocated_budget or 0

@frappe.whitelist()
def create_state_city():

    frappe.enqueue(
        job_name="Create State for Country",
        method=create_state,
        timeout=4000000,
    )

    frappe.enqueue(
        job_name="Create City for State",
        method=create_city,
        timeout=4000000,
    )

def create_state():
    country_state_list = ["Saudi Arabia", "Egypt", "India"]
    for country in country_state_list:
        url = "https://countriesnow.space/api/v0.1/countries/states"
        payload = {
            "country": country
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            return False
        
        data = response.json()['data']
        country_name = data['name']
        state_name_list = data['states']

        state_existing_list = frappe.get_all("State", {'country' : country_name}, pluck = "name")
        for state_name in state_name_list:
            if state_name not in state_existing_list:
                state_doc = frappe.new_doc("State")
                state_doc.state_province = state_name['name']
                state_doc.country = country
                state_doc.insert()
                state_existing_list.append(state_name['name'])
        frappe.db.commit()
    return True


def create_city():
    state_list = frappe.get_all("State", fields = ['name', 'country'])
    for state_dict in state_list:
        url = "https://countriesnow.space/api/v0.1/countries/state/cities"
        payload = {
            "country": state_dict['country'],
            "state" : state_dict['name']
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            return False
        
        city_name_list = response.json()['data']

        existing_city_list = frappe.get_all("City", {'state_province' : state_dict['country']}, pluck = "name")
        error_city_list = []
        for city in city_name_list:
            try:
                if city not in existing_city_list:
                    state_doc = frappe.new_doc("City")
                    state_doc.city_name = city
                    state_doc.state_province = state_dict['name']
                    state_doc.insert()
                    existing_city_list.append(city)
            except Exception as e:
                frappe.log_error("While Creating city", e)
                error_city_list.append(city)
            frappe.db.commit()
    return True
