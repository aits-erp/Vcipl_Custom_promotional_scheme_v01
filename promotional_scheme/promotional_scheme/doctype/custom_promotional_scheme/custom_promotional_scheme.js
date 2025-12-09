// ---------------------------------------
// Custom Promotional Scheme Doctype Script
// ---------------------------------------

frappe.ui.form.on("Custom Promotional Scheme", {
    onload(frm) {
        console.log("[CPS] onload");
        ensure_eligible_container(frm);
        render_eligible_schemes(frm);
    },

    refresh(frm) {
        console.log("[CPS] refresh");
        ensure_eligible_container(frm);
    },

    valid_from(frm) {
        console.log("[CPS] valid_from changed");
        render_eligible_schemes(frm);
    },

    valid_to(frm) {
        console.log("[CPS] valid_to changed");
        render_eligible_schemes(frm);
    },

    apply_on(frm) {
        if (frm.doc.apply_on === "Item Code") {
            if (frm.doc.promotional_scheme_on_item_group?.length > 0) {
                frappe.confirm(
                    "Switching to Item Code will remove Item Groups. Continue?",
                    () => {
                        frm.clear_table("promotional_scheme_on_item_group");
                        frm.refresh_field("promotional_scheme_on_item_group");
                    },
                    () => frm.set_value("apply_on", "Item Group")
                );
            }
        } else if (frm.doc.apply_on === "Item Group") {
            if (frm.doc.promotional_scheme_on_item_code?.length > 0) {
                frappe.confirm(
                    "Switching to Item Group will remove Item Codes. Continue?",
                    () => {
                        frm.clear_table("promotional_scheme_on_item_code");
                        frm.refresh_field("promotional_scheme_on_item_code");
                    },
                    () => frm.set_value("apply_on", "Item Code")
                );
            }
        }
    },

    type_of_promo_validation(frm) {
        frm.toggle_display("amount_discount_slabs_section", false);
        frm.toggle_display("quantity_discount_slabs_section", false);
        frm.toggle_display("quantity_with_free_amount_section", false);

        if (frm.doc.type_of_promo_validation === "Based on Minimum Amount") {
            frm.toggle_display("amount_discount_slabs_section", true);
        }

        if (frm.doc.type_of_promo_validation === "Based on Minimum Quantity") {
            frm.toggle_display("quantity_discount_slabs_section", true);
        }

        if (frm.doc.type_of_promo_validation === "Based on Minimum Quantity & Amount") {
            frm.toggle_display("quantity_with_free_amount_section", true);
        }
    },

    validate(frm) {
        if (frm.doc.apply_on === "Item Code" && frm.doc.promotional_scheme_on_item_group?.length > 0) {
            frappe.throw("Clear Item Groups before applying on Item Code.");
        }
        if (frm.doc.apply_on === "Item Group" && frm.doc.promotional_scheme_on_item_code?.length > 0) {
            frappe.throw("Clear Item Codes before applying on Item Group.");
        }
    }
});

// ---------------------------------------
// Eligible Schemes Renderer
// ---------------------------------------

function ensure_eligible_container(frm) {
    if (!frm.fields_dict || !frm.fields_dict.eligible_schemes_html) {
        console.warn("[CPS] eligible_schemes_html field NOT FOUND.");
        return;
    }
    const wrapper = $(frm.fields_dict.eligible_schemes_html.wrapper);

    if (wrapper.find("#eligible-schemes-container").length === 0) {
        wrapper.html(`
            <div id='eligible-schemes-container' style="
                padding: 8px;
                background: #fafafa;
                border: 1px dashed #d0d0d0;
            ">Eligible schemes will appear here.</div>
        `);
    }
}

function render_eligible_schemes(frm) {
    if (!frm.fields_dict.eligible_schemes_html) {
        console.warn("[CPS] HTML field missing");
        return;
    }

    const container = $(frm.fields_dict.eligible_schemes_html.wrapper)
        .find("#eligible-schemes-container");

    if (!frm.doc.valid_from || !frm.doc.valid_to) {
        container.html("<div class='text-muted small'>Enter both dates to find eligible schemes.</div>");
        return;
    }

    container.html("<div class='text-muted small'>Searching...</div>");

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Custom Promotional Scheme",
            fields: ["name", "scheme_name", "valid_from", "valid_to"],
            filters: [
                ["valid_from", "<=", frm.doc.valid_to],
                ["valid_to", ">=", frm.doc.valid_from]
            ],
            limit_page_length: 50
        },
        callback(r) {
            if (!r.message || r.message.length === 0) {
                container.html("<div class='text-muted small'>No schemes found for this date range.</div>");
                return;
            }

            let html = "<div style='padding:4px 0;'>";
            r.message.forEach(s => {
                html += `
                    <div data-name="${s.name}"
                         class="eligible-item"
                         style="padding:6px;border-bottom:1px solid #eee;cursor:pointer;">
                        <b>${frappe.utils.escape_html(s.scheme_name || s.name)}</b><br>
                        <span class='text-muted small'>
                            ${s.valid_from} → ${s.valid_to}
                        </span>
                    </div>
                `;
            });
            html += "</div><div class='small text-muted'>Click any scheme to open.</div>";

            container.html(html);

            container.find(".eligible-item").on("click", function () {
                const name = $(this).data("name");
                frappe.set_route("Form", "Custom Promotional Scheme", name);
            });
        }
    });
}
