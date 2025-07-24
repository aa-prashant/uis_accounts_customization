"""
Synchronise Account, Cost Center and Department trees from any *group* company
to every leaf company underneath it.

Key facts
─────────
•  Create / update / disable propagate
•  Rename propagates — duplicates eliminated
•  Deletes cascade to leaves
•  Edits / renames in leaf companies are rejected
•  Handles Cost‑Centre roots stored as "" or NULL
•  Unexpected errors logged with frappe.log_error
•  No augmented‑assignment operators
"""

from typing import List, Tuple, Optional
import frappe

DOCS = {"Account", "Cost Center", "Department"}

FLAG_TXN   = "_tree_sync_guard"           # recursion guard inside call stack
FLAG_RNAME = "_tree_sync_global_rename"   # “parent rename in progress”


# ──────────────────────────────────────────────────────────
# 1 ▸ VALIDATE – block edits in leaves (Accounts excluded)
# ──────────────────────────────────────────────────────────
def ensure_group_company(doc, method):
    if getattr(frappe.flags, FLAG_TXN, False) or doc.doctype not in DOCS:
        return
    if doc.doctype == "Account":
        return
    if frappe.db.get_value("Company", doc.company, "is_group") == 0:
        frappe.throw(f"Create or modify {doc.doctype} only in a *group* company.")


# ──────────────────────────────────────────────────────────
# 2 ▸ BEFORE_RENAME – block leaf rename + raise global flag
# ──────────────────────────────────────────────────────────
def block_leaf_rename(doc, method, *args, **kwargs):
    if getattr(frappe.flags, FLAG_TXN, False):
        return
    if doc.doctype not in {"Cost Center", "Department"}:
        return
    if frappe.db.get_value("Company", doc.company, "is_group") == 0:
        frappe.throw(f"Rename this {doc.doctype} in the parent company instead.")
    setattr(frappe.flags, FLAG_RNAME, True)      # suppress create‑logic during rename


# ──────────────────────────────────────────────────────────
# 3 ▸ AFTER_INSERT / ON_UPDATE – propagate create / update
#     (creates children only on *insert*, never on normal update)
# ──────────────────────────────────────────────────────────
def mirror(doc, method):
    if getattr(frappe.flags, FLAG_TXN, False) or doc.doctype not in DOCS:
        return
    if getattr(frappe.flags, FLAG_RNAME, False):       # ignore updates inside rename
        return

    comp = frappe.get_doc("Company", doc.company)
    if comp.is_group == 0:
        return

    leaves = frappe.get_all(
        "Company",
        filters={"is_group": 0, "lft": [">", comp.lft], "rgt": ["<", comp.rgt]},
        pluck="name",
    )

    allow_create = method == "after_insert"            # ← only inserts may create
    created, updated = [], []
    setattr(frappe.flags, FLAG_TXN, True)
    try:
        for leaf in leaves:
            c, u = _sync_to_leaf(doc, leaf, allow_create=allow_create)
            created.extend(c)
            updated.extend(u)
    finally:
        setattr(frappe.flags, FLAG_TXN, False)

    _toast(doc.doctype, created, updated)


# ──────────────────────────────────────────────────────────
# 4 ▸ AFTER_RENAME – propagate rename, clear global flag
# ──────────────────────────────────────────────────────────
def propagate_rename(doc, method, old_name: str, new_name: str, merge: bool):
    try:
        if getattr(frappe.flags, FLAG_TXN, False) or doc.doctype not in {"Cost Center", "Department"}:
            return

        parent_abbr = frappe.db.get_value("Company", doc.company, "abbr")
        base_old = old_name.removesuffix(f" - {parent_abbr}")
        base_new = new_name.removesuffix(f" - {parent_abbr}")

        comp = frappe.get_doc("Company", doc.company)
        if comp.is_group == 0:
            return

        abbrs = frappe.get_all(
            "Company",
            filters={"is_group": 0, "lft": [">", comp.lft], "rgt": ["<", comp.rgt]},
            pluck="abbr",
        )

        setattr(frappe.flags, FLAG_TXN, True)
        try:
            for abbr in abbrs:
                old_child = f"{base_old} - {abbr}"
                new_child = f"{base_new} - {abbr}"
                if frappe.db.exists(doc.doctype, old_child):
                    # frappe 15 signature
                    frappe.rename_doc(doc.doctype, old_child, new_child,
                                      force=1, merge=merge or False)
        finally:
            setattr(frappe.flags, FLAG_TXN, False)
        
        frappe.log_error(
            title="tree_sync propagate_rename call",
            message=f"{doc.doctype}\nparent_abbr={parent_abbr}\nold={old_name}\nnew={new_name}\n"
                    f"base_old={base_old} base_new={base_new}"
        )
        
    finally:
        setattr(frappe.flags, FLAG_RNAME, False)       # rename finished


# ──────────────────────────────────────────────────────────
# 5 ▸ ON_TRASH – cascade delete
# ──────────────────────────────────────────────────────────
def cascade_delete(doc, method):
    if getattr(frappe.flags, FLAG_TXN, False) or doc.doctype not in DOCS:
        return
    if frappe.db.get_value("Company", doc.company, "is_group") == 0:
        frappe.throw(f"Delete the {doc.doctype} in the parent company instead.")

    comp = frappe.get_doc("Company", doc.company)
    leaves = frappe.get_all(
        "Company",
        filters={"is_group": 0, "lft": [">", comp.lft], "rgt": ["<", comp.rgt]},
        pluck="name",
    )

    removed = []
    setattr(frappe.flags, FLAG_TXN, True)
    try:
        for leaf in leaves:
            child = frappe.db.get_value(
                doc.doctype,
                {"company": leaf, _name_field(doc.doctype): doc.get(_name_field(doc.doctype))},
                "name",
            )
            if child:
                frappe.delete_doc(doc.doctype, child, force=True, ignore_permissions=True)
                removed.append(leaf)
    finally:
        setattr(frappe.flags, FLAG_TXN, False)

    if removed:
        frappe.msgprint(f"{doc.doctype} deleted in: {', '.join(removed)}", alert=True)


# ──────────────────────────────────────────────────────────
# 6 ▸ Helper functions
# ──────────────────────────────────────────────────────────
def _sync_to_leaf(master, company, *, allow_create: bool) -> Tuple[List[str], List[str]]:
    created, updated = [], []
    parent = None
    for anc in reversed(_ancestors(master)):
        parent, new = _ensure_node(anc, company, parent, allow_create)
        if new:
            created.append(company)
    _, new = _ensure_node(master, company, parent, allow_create)
    (created if new else updated).append(company)
    return created, updated


def _ancestors(doc) -> List[frappe.model.document.Document]:
    parent_field = {"Account": "parent_account", "Cost Center": "parent_cost_center",
                    "Department": "parent_department"}[doc.doctype]
    chain, p = [], doc.get(parent_field)
    while p:
        pd = frappe.get_doc(doc.doctype, p)
        if doc.doctype == "Cost Center" and pd.get(parent_field) in ("", None):
            break
        chain.append(pd)
        p = pd.get(parent_field)
    return chain


def _ensure_node(src, company, parent, allow_create: bool) -> Tuple[str, bool]:
    if (src.doctype == "Department" and src.department_name == "All Departments") or \
       (src.doctype == "Cost Center" and src.parent_cost_center in ("", None)):
        return src.name, False

    key = _name_field(src.doctype)
    existing = frappe.db.get_value(src.doctype,
                                   {"company": company, key: src.get(key), "is_group": src.is_group},
                                   "name")
    if existing:
        _update_if_needed(src, existing, parent, company)
        return existing, False

    if not allow_create:
        return "", False                                    # ← skip creation on update

    payload = {"doctype": src.doctype, "company": company, key: src.get(key), "is_group": src.is_group}
    if src.doctype == "Cost Center" and not parent:
        parent = _root_cc(company)
    if parent:
        payload[{"Account": "parent_account", "Cost Center": "parent_cost_center",
                 "Department": "parent_department"}[src.doctype]] = parent
    if src.doctype == "Account":
        payload.update(account_type=src.account_type, root_type=src.root_type)

    new_doc = frappe.get_doc(payload)
    new_doc.insert(ignore_permissions=True)
    return new_doc.name, True


def _update_if_needed(src, tgt_name: str, parent: Optional[str], company: str):
    tgt = frappe.get_doc(src.doctype, tgt_name)
    dirty = False

    if src.doctype == "Account":
        for f in ("account_type", "root_type"):
            if getattr(tgt, f) != getattr(src, f):
                setattr(tgt, f, getattr(src, f)); dirty = True

    if tgt.is_group != src.is_group:
        tgt.is_group, dirty = src.is_group, True

    parent_field = {"Account": "parent_account", "Cost Center": "parent_cost_center",
                    "Department": "parent_department"}[src.doctype]
    if src.doctype == "Cost Center" and not parent:
        parent = _root_cc(company)
    if tgt.get(parent_field) != parent:
        tgt.set(parent_field, parent); dirty = True

    if dirty:
        tgt.save(ignore_permissions=True)


def _root_cc(company: str) -> str:
    return (frappe.db.get_value("Cost Center",
                                {"company": company, "is_group": 1, "parent_cost_center": ""},
                                "name")
            or frappe.db.get_value("Cost Center",
                                   {"company": company, "is_group": 1, "parent_cost_center": None},
                                   "name")
            or frappe.db.get_value("Cost Center", {"company": company, "lft": 1}, "name"))


def _name_field(dt: str) -> str:
    return {"Account": "account_name", "Cost Center": "cost_center_name",
            "Department": "department_name"}[dt]


def _toast(dt: str, created: List[str], updated: List[str]):
    if created or updated:
        rows = []
        if created:
            rows.append("Created → " + ", ".join(created))
        if updated:
            rows.append("Updated → " + ", ".join(updated))
        frappe.msgprint("<br>".join(rows), title=f"{dt} synchronised", alert=True)
