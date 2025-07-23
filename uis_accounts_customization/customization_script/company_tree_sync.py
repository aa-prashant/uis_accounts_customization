"""
Keep parent‑company trees (Account, Cost Center, Department) in sync
with every child company underneath the same lft/rgt span.
"""
import frappe
from typing import List, Tuple

SYNC_DOCTYPES = ["Account", "Cost Center", "Department"]


# ════════════════════════════════════════════════════════════════════════
#  Main hooks (one function works for all doctypes)
# ════════════════════════════════════════════════════════════════════════
def guard_and_sync(doc, method):
    """Run on validate / after_insert / on_update for the three doctypes."""
    comp = frappe.get_doc("Company", doc.company)

    # 1 ▸ Block edits in leaf companies
    if not comp.is_group:
        frappe.throw("Create or modify {0} only in a group company."
                     .format(doc.doctype))

    # 2 ▸ Scan children companies inside the tree
    child_companies = frappe.get_all(
        "Company",
        filters={
            "is_group": 0,
            "lft": [">", comp.lft],
            "rgt": ["<", comp.rgt],
        },
        pluck="name",
    )

    created, updated = [], []
    for child_company in child_companies:
        c, u = sync_tree(doc, child_company)
        created.extend(c)
        updated.extend(u)

    if created or updated:
        lines = []
        if created:
            lines.append("Created in {0}".format(", ".join(created)))
        if updated:
            lines.append("Updated in {0}".format(", ".join(updated)))
        frappe.msgprint("{0} synchronised:<br>{1}"
                        .format(doc.doctype, "<br>".join(lines)),
                        alert=True)


def prevent_child_delete(doc, method):
    if not frappe.db.get_value("Company", doc.company, "is_group"):
        frappe.throw("Delete the record in the parent (group) company instead.")
    # propagate delete to children
    child_companies = frappe.get_all(
        "Company",
        filters={
            "is_group": 0,
            "lft": [">", frappe.db.get_value("Company", doc.company, "lft")],
            "rgt": ["<", frappe.db.get_value("Company", doc.company, "rgt")],
        },
        pluck="name",
    )
    removed = []
    for comp in child_companies:
        name = frappe.db.get_value(doc.doctype,
                                   {"company": comp, "name": doc.name}, "name")
        if name:
            frappe.delete_doc(doc.doctype, name, force=True)
            removed.append(comp)

    if removed:
        frappe.msgprint("{0} deleted in: {1}"
                        .format(doc.doctype, ", ".join(removed)), alert=True)


# ════════════════════════════════════════════════════════════════════════
#  Tree synchronisation helpers
# ════════════════════════════════════════════════════════════════════════
def sync_tree(master, target_company) -> Tuple[List[str], List[str]]:
    """
    Ensure `master` (and its ancestors) exist in `target_company`.
    Returns (created_companies, updated_companies) lists for msgprint.
    """
    created, updated = [], []
    parent_name = None
    for ancestor in reversed(master.get_ancestors()):
        parent_name, was_created = ensure_node(
            ancestor, target_company, parent_name)
        if was_created:
            created.append("{0}:{1}".format(target_company, ancestor.account_name
                                            if master.doctype == "Account"
                                            else ancestor.name))

    leaf_name, was_created = ensure_node(master, target_company, parent_name)
    if was_created:
        created.append("{0}:{1}".format(target_company, master.get("account_name", leaf_name)))
    else:
        updated.append(target_company)

    return created, updated


def ensure_node(src_doc, company, parent_name) -> Tuple[str, bool]:
    """Create or update a single node.  Returns (name, was_created?)."""
    # Keys differ slightly by doctype:
    field_map = {
        "Account":     ("account_name", "account_type", "root_type", "is_group"),
        "Cost Center": ("cost_center_name", None, "is_group", None),
        "Department":  ("department_name", None, "is_group", None),
    }
    fname, ftype, froot, fisgrp = field_map[src_doc.doctype]

    filters = {
        "company": company,
        fname: src_doc.get(fname),
        "is_group": src_doc.is_group,
    }
    existing = frappe.db.get_value(src_doc.doctype, filters, "name")

    if existing:
        tgt = frappe.get_doc(src_doc.doctype, existing)
        tgt.is_group = src_doc.is_group
        if ftype:
            tgt.set(ftype, src_doc.get(ftype))
        if froot:
            tgt.set(froot, src_doc.get(froot))
        tgt.parent_ = parent_name
        if tgt.get_dirty_fields():
            tgt.save(ignore_permissions=True)
        return existing, False

    payload = {
        "doctype": src_doc.doctype,
        "company": company,
        fname: src_doc.get(fname),
        "is_group": src_doc.is_group,
        "parent_": parent_name,
    }
    if ftype:
        payload[ftype] = src_doc.get(ftype)
    if froot:
        payload[froot] = src_doc.get(froot)

    new_doc = frappe.get_doc(payload)
    new_doc.insert(ignore_permissions=True)
    return new_doc.name, True
