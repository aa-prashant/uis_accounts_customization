import frappe
import json

from frappe.utils import cint, cstr
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe import _, is_whitelisted
from frappe.utils.data import make_filter_tuple
from frappe.permissions import has_permission
from frappe.model.db_query import get_order_by
from frappe.desk.search import (
    get_std_fields_list,
    relevance_sorter,
    build_for_autosuggest,
    search_widget as std_search_widget,
)


def sanitize_searchfield(searchfield: str):
    if not searchfield:
        return

    if SPECIAL_CHAR_PATTERN.search(searchfield):
        frappe.throw(_("Invalid Search Field {0}").format(searchfield), frappe.DataError)


@frappe.whitelist()
def custom_search(
    doctype: str,
    txt: str,
    query: str | None = None,
    filters: str | dict | list | None = None,
    page_length: int = 10,
    searchfield: str | None = None,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    if (
        doctype in ["Customer", "Supplier"]
        and reference_doctype in ["Sales Order", "Quotation", "Purchase Order"]
        and filters
    ):
        filters = json.loads(filters)

        if reference_doctype in ["Sales Order", "Purchase Order"]:
            filters = [["Party Account", "company", "=", filters["company"][-1]]]

        elif reference_doctype == "Quotation":
            company_filter = filters.get("company")

            # company_filter might be a list or a plain string – normalise it
            if isinstance(company_filter, list):
                # examples: ['=', 'UIS Group']  OR  ['company', '=', 'UIS Group']
                if len(company_filter) == 3:
                    # already [field, op, value]
                    fieldname, operator, value = company_filter
                else:
                    # operator + value only → assume default fieldname = "company"
                    operator, value = company_filter
                    fieldname = "company"
            else:
                # simple string → assume '=' comparison
                fieldname = "company"
                operator = "="
                value = company_filter

            # build a valid filter (3‑tuple is fine; 4‑tuple also accepted)
            filters = [[fieldname, operator, value]]

        results = search_widget(
            doctype,
            txt.strip(),
            query,
            searchfield=searchfield,
            page_length=page_length,
            filters=filters,
            reference_doctype=reference_doctype,
            ignore_user_permissions=ignore_user_permissions,
        )
    else:
        results = std_search_widget(
            doctype,
            txt.strip(),
            query,
            searchfield=searchfield,
            page_length=page_length,
            filters=filters,
            reference_doctype=reference_doctype,
            ignore_user_permissions=ignore_user_permissions,
        )

    return build_for_autosuggest(results, doctype=doctype)


@frappe.whitelist()
def search_widget(
    doctype: str,
    txt: str,
    query: str | None = None,
    searchfield: str | None = None,
    start: int = 0,
    page_length: int = 10,
    filters: str | None | dict | list = None,
    filter_fields=None,
    as_dict: bool = False,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    start = cint(start)

    if isinstance(filters, str):
        filters = json.loads(filters)

    if searchfield:
        sanitize_searchfield(searchfield)

    if not searchfield:
        searchfield = "name"

    standard_queries = frappe.get_hooks().standard_queries or {}

    if not query and doctype in standard_queries:
        query = standard_queries[doctype][-1]

    if query:  # Query = custom search query i.e. python function
        try:
            is_whitelisted(frappe.get_attr(query))
            return frappe.call(
                query,
                doctype,
                txt,
                searchfield,
                start,
                page_length,
                filters,
                as_dict=as_dict,
                reference_doctype=reference_doctype,
                ignore_user_permissions=ignore_user_permissions,
            )
        except (frappe.PermissionError, frappe.AppNotInstalledError, ImportError):
            if frappe.local.conf.developer_mode:
                raise
            frappe.respond_as_web_page(
                title="Invalid Method",
                html="Method not found",
                indicator_color="red",
                http_status_code=404,
            )
            return []

    meta = frappe.get_meta(doctype)

    if filters is None:
        filters = []
    or_filters = []

    # build from doctype
    if txt:
        field_types = {
            "Data",
            "Text",
            "Small Text",
            "Long Text",
            "Link",
            "Select",
            "Read Only",
            "Text Editor",
        }
        search_fields = ["name"]
        if meta.title_field:
            search_fields.append(meta.title_field)

        if meta.search_fields:
            search_fields.extend(meta.get_search_fields())

        for f in search_fields:
            fmeta = meta.get_field(f.strip())
            if not meta.translated_doctype and (
                f == "name" or (fmeta and fmeta.fieldtype in field_types)
            ):
                or_filters.append([doctype, f.strip(), "like", f"%{txt}%"])

    if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
        filters.append([doctype, "enabled", "=", 1])
    if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
        filters.append([doctype, "disabled", "!=", 1])

    # format a list of fields combining search fields and filter fields
    fields = get_std_fields_list(meta, searchfield or "name")
    if filter_fields:
        fields = list(set(fields + json.loads(filter_fields)))
    formatted_fields = [f"`tab{meta.name}`.`{f.strip()}`" for f in fields]

    # Insert title field query after name
    if meta.show_title_field_in_link and meta.title_field:
        formatted_fields.insert(1, f"`tab{meta.name}`.{meta.title_field} as `label`")

    order_by_based_on_meta = get_order_by(doctype, meta)
    # `idx` is number of times a document is referred, check link_count.py
    order_by = f"`tab{doctype}`.idx desc, {order_by_based_on_meta}"

    if not meta.translated_doctype:
        _txt = frappe.db.escape((txt or "").replace("%", "").replace("@", ""))
        # locate returns 0 if string is not found, convert 0 to null and then sort null to end in order by
        _relevance = f"(1 / nullif(locate({_txt}, `tab{doctype}`.`name`), 0))"
        formatted_fields.append(f"""{_relevance} as `_relevance`""")
        # Since we are sorting by alias postgres needs to know number of column we are sorting
        if frappe.db.db_type == "mariadb":
            order_by = f"ifnull(_relevance, -9999) desc, {order_by}"
        elif frappe.db.db_type == "postgres":
            # Since we are sorting by alias postgres needs to know number of column we are sorting
            order_by = f"{len(formatted_fields)} desc nulls last, {order_by}"

    ignore_permissions = doctype == "DocType" or (
        cint(ignore_user_permissions)
        and has_permission(
            doctype,
            ptype="select" if frappe.only_has_select_perm(doctype) else "read",
            parent_doctype=reference_doctype,
        )
    )

    values = frappe.get_all(
        doctype,
        filters=filters,
        fields=formatted_fields,
        or_filters=or_filters,
        limit_start=start,
        limit_page_length=None if meta.translated_doctype else page_length,
        order_by=order_by,
        ignore_permissions=ignore_permissions,
        reference_doctype=reference_doctype,
        as_list=not as_dict,
        strict=False,
    )

    if meta.translated_doctype:
        # Filtering the values array so that query is included in very element
        values = (
            result
            for result in values
            if any(
                re.search(f"{re.escape(txt)}.*", _(cstr(value)) or "", re.IGNORECASE)
                for value in (result.values() if as_dict else result)
            )
        )

    # Sorting the values array so that relevant results always come first
    values = sorted(values, key=lambda x: relevance_sorter(x, txt, as_dict))

    # remove _relevance from results
    if not meta.translated_doctype:
        if as_dict:
            for r in values:
                r.pop("_relevance", None)
        else:
            values = [r[:-1] for r in values]

    return values
