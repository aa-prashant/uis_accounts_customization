app_name = "uis"
app_title = "Uis"
app_publisher = "Mohamed Elyamany"
app_description = "uis"
app_email = "m.elyamany@uis-services.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------
fixtures = [
    {
        "dt": "Custom Field", "filters": [
        [
            "module", "in", [
                "Uis"
            ]
        ]
        ]
    },
    {
        "dt": "Property Setter", "filters": [
        [
            "module", "in", [
                "Uis"
            ]
        ]
        ]
    },
]
# include js, css files in header of desk.html
# app_include_css = "/assets/uis/css/uis.css"
app_include_js = "uis.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/uis/css/uis.css"
# web_include_js = "/assets/uis/js/uis.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "uis/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Purchase Invoice" : "uis/custom/customization_dt/purchase_invoice.js",
    "Item Group":"uis/custom/customization_dt/item_group.js",
    "Address":"uis/custom/customization_dt/address.js",
    "Lead":"uis/custom/customization_dt/lead.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "uis/public/icons.svg"

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
# 	"methods": "uis.utils.jinja_methods",
# 	"filters": "uis.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "uis.install.before_install"
# after_install = "uis.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "uis.uninstall.before_uninstall"
# after_uninstall = "uis.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "uis.utils.before_app_install"
# after_app_install = "uis.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "uis.utils.before_app_uninstall"
# after_app_uninstall = "uis.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "uis.notifications.get_notification_config"

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
	"Sales Order": "uis.uis.custom.customization_script.sales_order.OverrideSalesOrder"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Purchase Invoice": {
		"on_submit": "uis.uis.custom.customization_script.purchase_invoice.on_submit",
        
	},
	"Journal Entry": {
		"on_submit": "uis.uis.custom.customization_script.journal_entry.on_submit",
        
	},
    "Purchase Order" : {
        "on_submit":"uis.uis.override.purchase_order.purchase_order.validate_budget",

    },
    "Asset Movement":{
        "before_insert" : "uis.uis.override.asset_movement.asset_movement.before_insert"
    },
    "*":{
        "validate": "uis.uis.custom.customization_script.handler.validate",
    }

}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"uis.tasks.all"
# 	],
# 	"daily": [
# 		"uis.tasks.daily"
# 	],
# 	"hourly": [
# 		"uis.tasks.hourly"
# 	],
# 	"weekly": [
# 		"uis.tasks.weekly"
# 	],
# 	"monthly": [
# 		"uis.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "uis.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "uis.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "uis.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["uis.utils.before_request"]
# after_request = ["uis.utils.after_request"]

# Job Events
# ----------
# before_job = ["uis.utils.before_job"]
# after_job = ["uis.utils.after_job"]

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
# 	"uis.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

