// Copyright (c) 2025, aits and contributors
// For license information, please see license.txt

frappe.ui.form.on("Custom Promotional Scheme", {
    apply_on: function(frm) {
        if (frm.doc.apply_on === "Item Code") {
            // If switched to Item Code, clear Item Group table
            if (frm.doc.promotional_scheme_on_item_group && frm.doc.promotional_scheme_on_item_group.length > 0) {
                frappe.confirm(
                    "You have existing Item Groups. Switching to Item Code will remove them. Continue?",
                    function() {
                        frm.clear_table("promotional_scheme_on_item_group");
                        frm.refresh_field("promotional_scheme_on_item_group");
                    },
                    function() {
                        // User cancelled — revert selection
                        frm.set_value("apply_on", "Item Group");
                    }
                );
            }
        } else if (frm.doc.apply_on === "Item Group") {
            // If switched to Item Group, clear Item Code table
            if (frm.doc.promotional_scheme_on_item_code && frm.doc.promotional_scheme_on_item_code.length > 0) {
                frappe.confirm(
                    "You have existing Item Codes. Switching to Item Group will remove them. Continue?",
                    function() {
                        frm.clear_table("promotional_scheme_on_item_code");
                        frm.refresh_field("promotional_scheme_on_item_code");
                    },
                    function() {
                        // User cancelled — revert selection
                        frm.set_value("apply_on", "Item Code");
                    }
                );
            }
        }
    },

    validate: function(frm) {
        // Safety validation on Save/Submit too
        if (frm.doc.apply_on === "Item Code" && frm.doc.promotional_scheme_on_item_group.length > 0) {
            frappe.throw("You have Item Groups added, but Apply On is set to Item Code. Please clear them.");
        }
        if (frm.doc.apply_on === "Item Group" && frm.doc.promotional_scheme_on_item_code.length > 0) {
            frappe.throw("You have Item Codes added, but Apply On is set to Item Group. Please clear them.");
        }
    }
});

