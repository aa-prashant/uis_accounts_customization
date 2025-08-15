import frappe
import json
import re  # used by translated-doctype branch in search_widget

from frappe.utils import cint, cstr
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe import _, is_whitelisted
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


# ------------------------ helpers ------------------------

def _safe_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return None
    return val


def _normalize_null_filters(val):
    """
    Convert [..., '=', None] -> [..., 'is', 'not set']
            [..., '!=', None] -> [..., 'is', 'set']
    Handles 3-tuple and 4-tuple filter rows.
    """
    if not isinstance(val, list):
        return val
    out = []
    i = 0
    n = len(val)
    while i < n:
        row = val[i]
        if isinstance(row, (list, tuple)):
            ln = len(row)
            if ln == 4:
                dt, field, op, v = row
                if v is None and op in ("=", "!="):
                    if op == "=":
                        out.append([dt, field, "is", "not set"])
                    else:
                        out.append([dt, field, "is", "set"])
                else:
                    out.append([dt, field, op, v])
            elif ln == 3:
                field, op, v = row
                if v is None and op in ("=", "!="):
                    if op == "=":
                        out.append([field, "is", "not set"])
                    else:
                        out.append([field, "is", "set"])
                else:
                    out.append([field, op, v])
            else:
                out.append(list(row))
        else:
            out.append(row)
        i = i + 1
    return out


def _extract_company_from_filters(parsed):
    """Extract plain company from dict-or-list style filters."""
    company_val = None
    if isinstance(parsed, dict):
        cv = parsed.get("company")
        if isinstance(cv, list):
            company_val = cv[-1] if len(cv) == 3 else (cv[1] if len(cv) >= 2 else None)
        else:
            company_val = cv
    elif isinstance(parsed, list):
        j = 0
        m = len(parsed)
        while j < m and not company_val:
            row = parsed[j]
            if isinstance(row, (list, tuple)):
                if len(row) == 3 and row[0] == "company":
                    company_val = row[2]
                elif len(row) == 4 and row[1] == "company":
                    company_val = row[3]
            j = j + 1
    return company_val


def _extract_company_from_doc_payload():
    """
    For new Payment Entry (unsaved), company is on the posted doc JSON: doc.company.
    Also works for child rows that carry parent info (parent/parenttype).
    """
    doc_json = frappe.form_dict.get("doc")
    if not doc_json:
        return None

    try:
        payload = json.loads(doc_json)
    except Exception:
        return None

    if isinstance(payload, dict):
        if payload.get("company"):
            return payload.get("company")
        if payload.get("parent") and payload.get("parenttype"):
            try:
                return frappe.db.get_value(payload.get("parenttype"), payload.get("parent"), "company")
            except Exception:
                return None
    return None


def _elog(title: str, data: dict):
    """Safe error logger (compact JSON)."""
    try:
        msg = frappe.as_json(data, indent=None)
        frappe.log_error(message=msg, title=title)
    except Exception:
        pass


def _peek_rows(rows, limit=3):
    """Return a tiny preview of result rows to avoid huge logs."""
    if not isinstance(rows, list):
        return None
    out = []
    i = 0
    n = len(rows)
    while i < n and i < limit:
        try:
            out.append(rows[i])
        except Exception:
            break
        i = i + 1
    return out


# ------------------------ main API ------------------------

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
    # A) Customer/Supplier for Sales Order / Quotation / Purchase Order (your existing behavior)
    if (
        doctype in ["Customer", "Supplier"]
        and reference_doctype in ["Sales Order", "Quotation", "Purchase Order"]
        and filters
    ):
        filters = json.loads(filters)

        if reference_doctype in ["Sales Order", "Purchase Order"]:
            company_name = filters["company"][-1]
            filters = [["Party Account", "company", "=", company_name]]

        elif reference_doctype == "Quotation":
            company_val = filters.get("company")
            if isinstance(company_val, list):
                if len(company_val) == 3:
                    company_val = company_val[-1]
                else:
                    company_val = company_val[1]
            filters = [["Party Account", "company", "=", company_val]]

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
        return build_for_autosuggest(results, doctype=doctype)

    # B) Payment Entry → Customer/Supplier/Employee/Shareholder (with detailed logs)
    if reference_doctype == "Payment Entry" and doctype in ["Customer", "Supplier", "Employee", "Shareholder"]:
        # Log the incoming call
        _elog("PE.enter", {
            "doctype": doctype,
            "txt": txt,
            "query_in": query,
            "filters_raw_type": type(filters).__name__ if filters is not None else "NoneType",
            "filters_raw_preview": filters if isinstance(filters, str) else frappe.as_json(filters, indent=None),
            "doc_json_present": bool(frappe.form_dict.get("doc")),
        })

        parsed = _safe_json(filters) if isinstance(filters, str) else filters

        # company from filters; if missing, try doc.company
        company_from_filters = _extract_company_from_filters(parsed)
        company_from_doc = None if company_from_filters else _extract_company_from_doc_payload()
        company_val = company_from_filters or company_from_doc

        _elog("PE.company_extracted", {
            "company_from_filters": company_from_filters,
            "company_from_doc": company_from_doc,
            "company_used": company_val,
        })

        pe_filters = []
        if company_val:
            if doctype in ["Customer", "Supplier"]:
                # Multi-company mapping via Party Account
                pe_filters.append(["Party Account", "company", "=", company_val])
            else:
                # Employee / Shareholder: direct company field
                pe_filters.append([doctype, "company", "=", company_val])

        _elog("PE.before_search", {
            "doctype": doctype,
            "query_used": None,  # we call our own search_widget, not a core query
            "final_filters": pe_filters,
            "page_length": page_length,
        })

        # Use our internal search so the filter is honored (skip any version-specific core queries)
        results = search_widget(
            doctype,
            txt.strip(),
            None,
            searchfield=searchfield,
            page_length=page_length,
            filters=pe_filters,
            reference_doctype=reference_doctype,
            ignore_user_permissions=ignore_user_permissions,
        )

        _elog("PE.after_search", {
            "result_count": len(results) if isinstance(results, list) else None,
            "result_peek": _peek_rows(results, limit=3),
        })

        return build_for_autosuggest(results, doctype=doctype)

    # C) Default path — sanitize bad null comparisons first (fixes Sales Person traceback)
    sanitized = filters
    if isinstance(sanitized, str):
        sanitized = _safe_json(sanitized)
    sanitized = _normalize_null_filters(sanitized) if isinstance(sanitized, list) else sanitized

    results = std_search_widget(
        doctype,
        txt.strip(),
        query,
        searchfield=searchfield,
        page_length=page_length,
        filters=sanitized,
        reference_doctype=reference_doctype,
        ignore_user_permissions=ignore_user_permissions,
    )
    return build_for_autosuggest(results, doctype=doctype)


# ------------------------ local search (unchanged) ------------------------

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

    if query:
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

    fields = get_std_fields_list(meta, searchfield or "name")
    if filter_fields:
        fields = list(set(fields + json.loads(filter_fields)))
    formatted_fields = [f"`tab{meta.name}`.`{f.strip()}`" for f in fields]

    if meta.show_title_field_in_link and meta.title_field:
        formatted_fields.insert(1, f"`tab{meta.name}`.{meta.title_field} as `label`")

    order_by_based_on_meta = get_order_by(doctype, meta)
    order_by = f"`tab{doctype}`.idx desc, {order_by_based_on_meta}"

    if not meta.translated_doctype:
        _txt = frappe.db.escape((txt or "").replace("%", "").replace("@", ""))
        _relevance = f"(1 / nullif(locate({_txt}, `tab{doctype}`.`name`), 0))"
        formatted_fields.append(f"{_relevance} as `_relevance`")
        if frappe.db.db_type == "mariadb":
            order_by = f"ifnull(_relevance, -9999) desc, {order_by}"
        elif frappe.db.db_type == "postgres":
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
        values = (
            result
            for result in values
            if any(
                re.search(f"{re.escape(txt)}.*", _(cstr(value)) or "", re.IGNORECASE)
                for value in (result.values() if as_dict else result)
            )
        )

    values = sorted(values, key=lambda x: relevance_sorter(x, txt, as_dict))

    if not meta.translated_doctype:
        if as_dict:
            for r in values:
                r.pop("_relevance", None)
        else:
            values = [r[:-1] for r in values]

    return values