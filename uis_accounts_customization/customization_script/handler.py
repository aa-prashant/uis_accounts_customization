import frappe
from frappe.utils import cint

# ------------------------------------------------------------------------- #
# ❶  Main validate hook
# ------------------------------------------------------------------------- #
def validate(doc, method):
    """
    • Propagate accounting-dimension values from parent → child rows
    • Enforce mandatory accounting-dimension presence & company correctness
    """

    # Skip meta / system doctypes or docs without a company
    if (
        not doc.get("company")
        or doc.doctype
        in (
            "DocType",
            "Version",
            "Custom Field",
            "Property Setter",
            "Portal Settings",
            "Installed Applications",
        )
    ):
        return

    # 1️⃣  Auto-fill children that are missing dimensions
    propagate_dimensions_from_parent(doc)

    # 2️⃣  Mandatory / validity checks (same as before)
    meta_cache = {}  # <doctype>  →  [valid record names]
    error = get_meta_info(doc, meta_cache)

    for table_field in (
        f for f, v in doc.as_dict().items() if isinstance(v, list)
    ):
        for row in doc.get(table_field):
            error += get_meta_info(row, meta_cache, is_child=True)

    if error:
        frappe.throw(error)

# ------------------------------------------------------------------------- #
# ❷  Utility: propagate dimensions
# ------------------------------------------------------------------------- #
DIMENSIONS = {"branch", "cost_center", "department", "project"}

def propagate_dimensions_from_parent(doc):
    """
    Copy each dimension from parent → child row **once**
    (only when child field is blank / falsy).
    """
    parent_dims = {fld: doc.get(fld) for fld in DIMENSIONS if doc.get(fld)}

    if not parent_dims:
        return  # Nothing to copy

    for table_field in (
        f for f, v in doc.as_dict().items() if isinstance(v, list)
    ):
        for row in doc.get(table_field):
            # ensure row has the field before setting
            for fld, val in parent_dims.items():
                if fld in row.as_dict() and not row.get(fld):
                    row.set(fld, val)

# ------------------------------------------------------------------------- #
# ❸  Utility: validate dimensions
# ------------------------------------------------------------------------- #
def get_meta_info(
    record,
    meta_cache: dict,
    is_child: bool = False,
) -> str:
    """
    Return HTML string listing any problems for *record*.
    Uses meta_cache to avoid repetitive DB hits.
    """

    meta = frappe.get_meta(record.doctype)
    problems = []

    for df in meta.fields:
        fieldname = df.fieldname
        if df.fieldtype == "Data" or fieldname not in DIMENSIONS:
            continue

        label = frappe.bold(df.label)

        # -- 1. Missing value -------------------------------------------------
        if not record.get(fieldname):
            prefix = f"{record.doctype} : Row {record.idx}, " if is_child else ""
            problems.append(f"{prefix}{label} is a mandatory field<br>")
            continue

        # -- 2. Ensure linked value belongs to same company -------------------
        doctype = df.options
        if doctype not in meta_cache:
            meta_cache[doctype] = frappe.get_all(
                doctype, {"company": record.company}, pluck="name"
            )

        if record.get(fieldname) not in meta_cache[doctype]:
            prefix = f"{record.doctype} : Row {record.idx}, " if is_child else ""
            problems.append(
                f"{prefix}Incorrect value in {label} field<br>"
            )

    return "".join(problems)