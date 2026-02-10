# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Uis Accounts Customization** is a Frappe custom app for accounts-related customizations. It handles company-wide tree synchronization for Account/Cost Center/Department structures and provides specialized validation and search enhancements.

## App Structure

| Directory | Description |
|-----------|-------------|
| `customization_js/` | Doctype-specific JavaScript files (Sales Invoice, Purchase Invoice, Lead, Item Group, etc.) |
| `customization_script/` | Python modules for doc_events hooks and business logic |
| `overrides/doctype/` | Override JS/Python for standard doctypes (Address, Payment Entry, Travel Request) |
| `other_customization/` | DocType definitions (Custom Fields, Property Setters, Client Scripts) |
| `api/` | Whitelisted API endpoints (custom_search.py) |
| `fixtures/` | Data fixtures (custom_field, property_setter, client_script) |

## Key Architecture Patterns

### Company Tree Synchronization (`company_tree_sync.py`)

Synchronizes Account, Cost Center, and Department trees from group companies to leaf companies:

- **Mirror on create/update**: Changes in parent propagate to all leaf companies
- **Rename propagation**: Base name preserved, company abbreviation updated per leaf
- **Cascade delete**: Deleting in parent removes from all leaves
- **Leaf protection**: Edits/renames in leaf companies are blocked
- Uses `frappe.flags._tree_sync_guard` and `_tree_sync_global_rename` flags to prevent recursion

### Document Validation (`handler.py`)

Global validate hook that:
- Auto-fills branch, cost_center, department, project from parent to child rows
- Ensures accounting dimensions have correct values per company
- Special handling for Sales Order (project optional) and Asset Movement (branch/department skipped)

### Custom Search (`custom_search.py`)

Overrides `frappe.desk.search.search_link` to:
- Filter Customer/Supplier by Party Account company for Sales Order/Purchase Order/Quotation
- Filter Payment Entry links (Customer, Supplier, Employee, Shareholder) by company via Party Account or direct company field
- Handle null filter normalization (= None → "is not set")

### Address Customization (`overrides/doctype/address/`)

Custom state/city filtering via Google Maps integration:
- Dependent state-province and city dropdowns
- Google Maps URL parsing to extract lat/lng
- Leaflet map with Carto Voyager tiles
- View in Google Maps button

## Development Commands

```bash
# Run tests
bench run-tests --app uis_accounts_customization

# Format and lint
ruff format uis_accounts_customization/
ruff check --select I --fix uis_accounts_customization/
```

## Fixtures

Registered in `hooks.py`:
- **Custom Field**: "Other Customization" module
- **Property Setter**: "Other Customization", "Uis Accounts Customization" modules
- **Client Script**: "Other Customization", "Uis Accounts Customization" modules

## DocType Overrides

**JavaScript hooks** (`doctype_js`):
- Purchase Invoice, Item Group, Address, Lead, Journal Entry, Sales Invoice
- Travel Request, Payment Entry (overrides)

**Python overrides** (`override_doctype_class`):
- Sales Order → `OverrideSalesOrder`

**Document Events** (`doc_events`):
- Purchase Invoice → on_submit
- Journal Entry → on_submit
- Purchase Order → on_submit (validate_budget)
- Asset Movement → before_insert
- Asset Depreciation Schedule → before_insert
- Account, Cost Center, Department → validate, before_rename, after_insert, on_update, after_rename, on_trash
- Address → before_save (set_address_lines, set_address_title)
- All doctypes → validate (handler.validate)
