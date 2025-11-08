// Copyright (c) 2025, aits and contributors
// For license information, please see license.txt

frappe.query_reports["Custom Promotional Scheme Report"] = {
    "filters": [
        {
            "fieldname": "scheme_name",
            "label": __("Scheme Name"),
            "fieldtype": "Link",
            "options": "Custom Promotional Scheme"
        },
        {
            "fieldname": "party_type",
            "label": __("Party Type"),
            "fieldtype": "Select",
            "options": ["", "Customer", "Supplier"]
        },
        {
            "fieldname": "party_name",
            "label": __("Party"),
            "fieldtype": "Link",
            "options": "",        // will be dynamic based on party_type (see note below)
            "dependencies": ["party_type"]
        },
        {
            "fieldname": "apply_on",
            "label": __("Apply On"),
            "fieldtype": "Select",
            "options": ["", "Item Code", "Item Group"]
        },
        {
            "fieldname": "item_or_group",
            "label": __("Item or Item Group"),
            "fieldtype": "Data",
            "description": "Enter item code or item group fragment to filter"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "min_invoice_amount",
            "label": __("Min Invoice Amount"),
            "fieldtype": "Currency"
        },
        {
            "fieldname": "max_invoice_amount",
            "label": __("Max Invoice Amount"),
            "fieldtype": "Currency"
        },
        {
            "fieldname": "min_invoice_qty",
            "label": __("Min Invoice Qty"),
            "fieldtype": "Float"
        },
        {
            "fieldname": "max_invoice_qty",
            "label": __("Max Invoice Qty"),
            "fieldtype": "Float"
        },
        {
            "fieldname": "discount_min",
            "label": __("Discount % Min"),
            "fieldtype": "Float"
        },
        {
            "fieldname": "discount_max",
            "label": __("Discount % Max"),
            "fieldtype": "Float"
        },
        {
            "fieldname": "show_only_eligible",
            "label": __("Show Only Eligible"),
            "fieldtype": "Check",
            "default": 1
        }
    ],

    // Optional: dynamically set party_name options when party_type changes
    // onload: function(report) {
    //     const party_field = report.fields_dict.party_type;
    //     const party_name_field = report.fields_dict.party_name;
    //     if (!party_field || !party_name_field) return;

    //     party_field.df.onchange = function() {
    //         const val = party_field.get_value();
    //         if (val === "Supplier") {
    //             party_name_field.df.options = "Supplier";
    //         } else if (val === "Customer") {
    //             party_name_field.df.options = "Customer";
    //         } else {
    //             party_name_field.df.options = "";
    //         }
    //         party_name_field.refresh();
    //     };
    // }
};
