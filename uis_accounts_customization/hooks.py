app_name = "uis_accounts_customization"
app_title = "Uis Accounts Customization"
app_publisher = "Actinoids-IO"
app_description = "Accounts Description"
app_email = "hello@actinoids-io.in"
app_license = "mit"

# Includes in <head>
# ------------------
fixtures = [
    {
        "dt": "Custom Field", "filters": [
        [
            "module", "in", [
                "Other Customization"
            ]
        ]
        ]
    },
    {
        "dt": "Property Setter", "filters": [
        [
            "module", "in", [
                "Other Customization", "Uis Accounts Customization"
            ],
            
        ]
        ]
    },
    {
        "dt": "Client Script", "filters": [
        [
            "module", "in", [
                "Other Customization", "Uis Accounts Customization"
            ],
            
        ]
        ]
    },
]


# include js, css files in header of desk.html
# app_include_css = "/assets/uis/css/uis.css"
app_include_js = "uis_accounts_customization.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/uis_accounts_customization/css/uis_accounts_customization.css"
# web_include_js = "/assets/uis_accounts_customization/js/uis_accounts_customization.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "uis_accounts_customization/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Purchase Invoice" : "customization_js/purchase_invoice.js",
    "Item Group":"customization_js/item_group.js",
    "Address":"overrides/doctype/address/address.js",
    "Lead":"customization_js/lead.js",
    "Journal Entry":"customization_js/journal_entry.js",
    "Sales Invoice":"customization_js/sales_invoice.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "uis_accounts_customization/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "uis_accounts_customization.utils.jinja_methods",
# 	"filters": "uis_accounts_customization.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "uis_accounts_customization.install.before_install"
# after_install = "uis_accounts_customization.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "uis_accounts_customization.uninstall.before_uninstall"
# after_uninstall = "uis_accounts_customization.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "uis_accounts_customization.utils.before_app_install"
# after_app_install = "uis_accounts_customization.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "uis_accounts_customization.utils.before_app_uninstall"
# after_app_uninstall = "uis_accounts_customization.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "uis_accounts_customization.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Sales Order": "uis_accounts_customization.customization_script.sales_order.OverrideSalesOrder"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Purchase Invoice": {
		"on_submit": "uis_accounts_customization.customization_script.purchase_invoice.on_submit",
        
	},
	"Journal Entry": {
		"on_submit": "uis_accounts_customization.customization_script.journal_entry.on_submit",
        
	},
    "Purchase Order" : {
        "on_submit":"uis_accounts_customization.customization_script.purchase_order.purchase_order.validate_budget",

    },
    "Asset Movement":{
        "before_insert" : "uis_accounts_customization.customization_script.asset_movement.asset_movement.before_insert"
    },
    "Asset Depreciation Schedule":{
        "before_insert" : "uis_accounts_customization.customization_script.asset_depericiation_schedule.asset_depreciation_schedule.before_insert"
    },
    "*":{
        "validate": "uis_accounts_customization.customization_script.handler.validate",
    },
    "Address": {
        "before_save":"uis_accounts_customization.overrides.doctype.address.address.set_address_lines"
    },
    # "Cost Center" : {
    #     "after_insert":"uis_accounts_customization.customization_script.cost_center.db_insert",
    # },
    # "Department" : {
    #     "after_insert":"uis_accounts_customization.customization_script.department.db_insert",

    # },
}

for dt in ["Account", "Cost Center", "Department"]:
    doc_events[dt] = {
        "validate":      "uis_accounts_customization.customization_script.company_tree_sync.ensure_group_company",
        "before_rename": "uis_accounts_customization.customization_script.company_tree_sync.block_leaf_rename",
        "after_insert":  "uis_accounts_customization.customization_script.company_tree_sync.mirror",
        "on_update":     "uis_accounts_customization.customization_script.company_tree_sync.mirror",
        "after_rename":  "uis_accounts_customization.customization_script.company_tree_sync.propagate_rename",
        "on_trash":      "uis_accounts_customization.customization_script.company_tree_sync.cascade_delete",
    }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"uis_accounts_customization.tasks.all"
# 	],
# 	"daily": [
# 		"uis_accounts_customization.tasks.daily"
# 	],
# 	"hourly": [
# 		"uis_accounts_customization.tasks.hourly"
# 	],
# 	"weekly": [
# 		"uis_accounts_customization.tasks.weekly"
# 	],
# 	"monthly": [
# 		"uis_accounts_customization.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "uis_accounts_customization.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.search.search_link": "uis_accounts_customization.api.custom_search.custom_search"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "uis_accounts_customization.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["uis_accounts_customization.utils.before_request"]
# after_request = ["uis_accounts_customization.utils.after_request"]

# Job Events
# ----------
# before_job = ["uis_accounts_customization.utils.before_job"]
# after_job = ["uis_accounts_customization.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"uis_accounts_customization.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

