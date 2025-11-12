# Copyright (c) 2025, aits and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, flt, getdate


class CustomPromotionalScheme(Document):
    def validate(self):
        self.validate_dates()
        self.validate_condition_fields()
        self.validate_apply_on_exclusivity()

    def validate_apply_on_exclusivity(self):
        if self.apply_on == "Item Code" and self.promotional_scheme_on_item_group:
            frappe.throw("You selected 'Item Code' but added rows in 'Promotional scheme on item group'. Please clear them.")
        if self.apply_on == "Item Group" and self.promotional_scheme_on_item_code:
            frappe.throw("You selected 'Item Group' but added rows in 'Promotional scheme on item code'. Please clear them.")

    def validate_dates(self):
        if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
            frappe.throw("Valid From date cannot be later than Valid To date.")

    def validate_condition_fields(self):
        """Ensure selected validation type has required fields."""
        if self.type_of_promo_validation == "Based on Minimum Amount":
            if not self.minimum_amount or not self.discount_percentage:
                frappe.throw("Please specify both Minimum Amount and Discount Percentage.")
        elif self.type_of_promo_validation == "Based on Minimum Quantity":
            if not self.minimum_quantity or not self.free_quantity:
                frappe.throw("Please specify both Minimum Quantity and Free Quantity.")

    @staticmethod
    def get_active_schemes_for_party(party_type):
        """Return list of active scheme names for party_type (Selling/Buying)."""
        today = getdate(nowdate())
        return frappe.get_all(
            "Custom Promotional Scheme",
            filters={
                "select_the_party": party_type,
                "valid_from": ["<=", today],
                "valid_to": [">=", today]
            },
            pluck="name"
        )


# -------------------------
# Utility helpers
# -------------------------
def _extract_values_from_child_rows(doc, fieldname, possible_keys=None):
    """
    Generic extractor for child table fields / multiselect child rows.
    - doc: frappe.get_doc(...) for the scheme
    - fieldname: the child table fieldname on scheme doc (e.g. 'customer', 'customer_group', 'promotional_scheme_on_item_code')
    - possible_keys: list of keys to attempt per row (e.g. ['customer', 'item', 'item_code'])
    Returns a set of string values (empty set if none).
    """
    vals = set()
    possible_keys = possible_keys or []
    rows = doc.get(fieldname) or []
    # If it's a plain list of strings (some multiselect styles), handle that:
    if isinstance(rows, list) and rows and isinstance(rows[0], str):
        for v in rows:
            vals.add(str(v))
        return vals

    # Otherwise expect rows are dict-like child rows
    for row in rows:
        # row might be a Document or dict
        row_dict = row.as_dict() if hasattr(row, "as_dict") else dict(row)
        # try the provided keys
        for k in possible_keys:
            if k in row_dict and row_dict.get(k):
                vals.add(str(row_dict.get(k)))
                break
        # fallback: if only one field present (like Table MultiSelect using 'item'), pick it
        else:
            # take first textual field that looks useful
            for k2, v2 in row_dict.items():
                if k2 in ("idx", "name", "parent", "parentfield", "parenttype", "doctype"):
                    continue
                if v2:
                    vals.add(str(v2))
                    break
    return vals


def _extract_item_codes_from_scheme(scheme_doc):
    """
    Extract item codes that scheme applies on.
    It will inspect expected fields on scheme doc:
      - promotional_scheme_on_item_code (child rows) -> look for 'item_code' or 'item'
      - promotional_scheme_on_item_group (child rows) -> look for 'item_group' or 'group'
    Returns a set of item codes (strings). If item_group rows found, expands to actual Items by querying Item doctype.
    """
    item_codes = set()

    # item_code child rows (likely child doctype like Pricing Rule Item Code)
    item_code_vals = _extract_values_from_child_rows(
        scheme_doc,
        "promotional_scheme_on_item_code",
        possible_keys=["item_code", "item"]
    )
    item_codes.update(item_code_vals)

    # item groups -> find items with those groups
    item_group_vals = _extract_values_from_child_rows(
        scheme_doc,
        "promotional_scheme_on_item_group",
        possible_keys=["item_group", "group"]
    )
    if item_group_vals:
        # Query Item by item_group
        items = frappe.get_all("Item", filters={"item_group": ["in", list(item_group_vals)]}, pluck="name")
        item_codes.update(items or [])

    return item_codes


def _extract_party_values_from_scheme(scheme_doc):
    """
    Extract party lists from scheme_doc in a robust way.
    Returns dict with keys: customers, customer_groups, territories, suppliers, supplier_groups (each is a set).
    """
    customers = _extract_values_from_child_rows(scheme_doc, "customer", possible_keys=["customer", "item", "value"])
    customer_groups = _extract_values_from_child_rows(scheme_doc, "customer_group", possible_keys=["customer_group", "item", "value", "group"])
    territories = _extract_values_from_child_rows(scheme_doc, "territory", possible_keys=["territory", "item", "value"])
    suppliers = _extract_values_from_child_rows(scheme_doc, "supplier", possible_keys=["supplier", "item", "value"])
    supplier_groups = _extract_values_from_child_rows(scheme_doc, "supplier_group", possible_keys=["supplier_group", "item", "value", "group"])

    return {
        "customers": customers,
        "customer_groups": customer_groups,
        "territories": territories,
        "suppliers": suppliers,
        "supplier_groups": supplier_groups,
    }


# -------------------------
# Main Hook: called on submit of invoices
# -------------------------
def apply_promotional_schemes(doc, method):
    """
    Hook to be called on_submit of Sales Invoice and Purchase Invoice.
    Checks all active schemes and applies matching ones (party + item).
    """
    if doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
        return

    party_side = "Selling" if doc.doctype == "Sales Invoice" else "Buying"
    active_scheme_names = CustomPromotionalScheme.get_active_schemes_for_party(party_side)
    if not active_scheme_names:
        return

    # For each scheme, load full doc and evaluate
    for scheme_name in active_scheme_names:
        try:
            scheme_doc = frappe.get_doc("Custom Promotional Scheme", scheme_name)
        except Exception:
            # skip invalid scheme docs
            continue

        # 1) Party match: if scheme has any party selectors, invoice must match at least one
        parties = _extract_party_values_from_scheme(scheme_doc)
        if not _invoice_party_matches(doc, parties):
            # scheme isn't meant for this invoice party
            continue

        # 2) Item match: determine item codes the scheme concerns
        item_codes = _extract_item_codes_from_scheme(scheme_doc)
        # If scheme has no items specified (empty), interpret as "all items" (apply to any items)
        if item_codes:
            matching_items = [it for it in doc.items if getattr(it, "item_code", None) in item_codes]
        else:
            # no item restrictions -> all invoice items considered
            matching_items = list(doc.items)

        if not matching_items:
            # no items from invoice match scheme
            continue

        # 3) Apply validation logic (amount or quantity)
        if scheme_doc.type_of_promo_validation == "Based on Minimum Amount":
            total_without_gst = flt(sum(getattr(it, "base_net_amount", 0) or 0 for it in matching_items))
            if total_without_gst >= flt(scheme_doc.minimum_amount or 0):
                discount_pct = flt(scheme_doc.discount_percentage or 0)
                if discount_pct > 0:
                    apply_discount_to_invoice(doc, matching_items, discount_pct, scheme_doc.name)
        elif scheme_doc.type_of_promo_validation == "Based on Minimum Quantity":
            total_qty = flt(sum(getattr(it, "qty", 0) or 0 for it in matching_items))
            if total_qty >= flt(scheme_doc.minimum_quantity or 0):
                free_qty = flt(scheme_doc.free_quantity or 0)
                if free_qty > 0:
                    add_free_items_to_invoice(doc, matching_items, free_qty, scheme_doc.name)


# -------------------------
# Helpers used above
# -------------------------
def _invoice_party_matches(doc, parties_dict):
    """
    Given invoice `doc` and `parties_dict` returned by _extract_party_values_from_scheme,
    determine if invoice party matches scheme criteria.
    If the scheme defines no parties at all (all sets empty), treat as match (applies to all).
    """
    # if scheme contains no party limitations -> treat as global (match)
    has_any_party_limit = any(len(v) > 0 for v in parties_dict.values())
    if not has_any_party_limit:
        return True

    # Sales Invoice checks
    if doc.doctype == "Sales Invoice":
        # If customers set defined and invoice.customer not in it -> fail
        if parties_dict["customers"] and (not getattr(doc, "customer", None) or str(doc.customer) not in parties_dict["customers"]):
            return False
        if parties_dict["customer_groups"] and (not getattr(doc, "customer_group", None) or str(doc.customer_group) not in parties_dict["customer_groups"]):
            return False
        if parties_dict["territories"] and (not getattr(doc, "territory", None) or str(doc.territory) not in parties_dict["territories"]):
            return False

    # Purchase Invoice checks
    if doc.doctype == "Purchase Invoice":
        if parties_dict["suppliers"] and (not getattr(doc, "supplier", None) or str(doc.supplier) not in parties_dict["suppliers"]):
            return False
        if parties_dict["supplier_groups"] and (not getattr(doc, "supplier_group", None) or str(doc.supplier_group) not in parties_dict["supplier_groups"]):
            return False

    return True


def apply_discount_to_invoice(doc, matching_items, discount_pct, scheme_name):
    """
    Apply discount_pct to matching_items by reducing item.rate and marking item row.
    Note: calling code runs during on_submit; changes will be saved in the same document.
    """
    for it in matching_items:
        original_rate = flt(getattr(it, "rate", 0))
        discount_value = original_rate * (discount_pct / 100.0)
        it.rate = flt(original_rate - discount_value)
        # set discount fields if available
        try:
            it.discount_percentage = discount_pct
        except Exception:
            pass
        try:
            it.promotional_scheme_applied = scheme_name
        except Exception:
            pass

    frappe.msgprint(f"✅ Promotional Scheme '{scheme_name}' applied: {discount_pct}% discount.")


def add_free_items_to_invoice(doc, matching_items, free_qty, scheme_name):
    """
    Add additional free item rows (zero rate) equal to free_qty for each matched item.
    If you prefer to add only once per scheme, modify this accordingly.
    """
    for it in matching_items:
        # create new child row dict
        new_row = {
            "item_code": getattr(it, "item_code", None),
            "item_name": getattr(it, "item_name", None),
            "qty": free_qty,
            "rate": 0,
            "amount": 0,
            "base_rate": 0,
            "base_amount": 0,
            "is_free_item": 1,
        }
        # optional marker
        try:
            new_row["promotional_scheme_applied"] = scheme_name
        except Exception:
            pass

        # append to items table
        doc.append("items", new_row)

    frappe.msgprint(f"🎁 Free Quantity ({free_qty})  '{scheme_name}'.")

# import frappe
# from frappe.model.document import Document
# from frappe.utils import nowdate, flt, getdate


# class CustomPromotionalScheme(Document):
#     def validate(self):
#         self.validate_dates()
#         self.validate_condition_fields()

#     def validate_dates(self):
#         if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
#             frappe.throw("Valid From date cannot be later than Valid To date.")

#     def validate_condition_fields(self):
#         """Ensure only one condition type is used: minimum amount or minimum quantity"""
#         if self.type_of_promo_validation == "Based on Minimum Amount":
#             if not self.minimum_amount or not self.discount_percentage:
#                 frappe.throw("Please specify both Minimum Amount and Discount Percentage.")
#         elif self.type_of_promo_validation == "Based on Minimum Quantity":
#             if not self.minimum_quantity or not self.free_quantity:
#                 frappe.throw("Please specify both Minimum Quantity and Free Quantity.")

#     @staticmethod
#     def get_applicable_schemes(party_type):
#         """Fetch active schemes (valid today) for given party type (Selling/Buying)."""
#         today = getdate(nowdate())
#         return frappe.get_all(
#             "Custom Promotional Scheme",
#             filters={
#                 "select_the_party": party_type,
#                 "valid_from": ["<=", today],
#                 "valid_to": [">=", today],
#             },
#             fields=["name", "apply_on", "type_of_promo_validation", "minimum_amount",
#                     "discount_percentage", "minimum_quantity", "free_quantity"]
#         )


# def apply_promotional_schemes(doc, method):
#     """
#     Hook triggered when Sales/Purchase Invoice is submitted.
#     Checks if invoice qualifies for any active scheme and applies discount logic.
#     """
#     if doc.doctype not in ["Sales Invoice", "Purchase Invoice"]:
#         return

#     party_type = "Selling" if doc.doctype == "Sales Invoice" else "Buying"

#     # Get all active schemes for this party type
#     schemes = CustomPromotionalScheme.get_applicable_schemes(party_type)
#     if not schemes:
#         return

#     for scheme in schemes:
#         # Get related items/groups for this scheme
#         item_list = []
#         if scheme.apply_on == "Item Code":
#             item_list = frappe.get_all(
#                 "Pricing Rule Item Code",
#                 filters={"parent": scheme.name},
#                 pluck="item_code"
#             )
#         elif scheme.apply_on == "Item Group":
#             groups = frappe.get_all(
#                 "Pricing Rule Item Group",
#                 filters={"parent": scheme.name},
#                 pluck="item_group"
#             )
#             if groups:
#                 item_list = frappe.get_all(
#                     "Item",
#                     filters={"item_group": ["in", groups]},
#                     pluck="name"
#                 )

#         # Filter invoice items that match scheme criteria
#         matching_items = [
#             d for d in doc.items if d.item_code in item_list
#         ]

#         if not matching_items:
#             continue

#         # --- Check eligibility based on scheme type ---
#         if scheme.type_of_promo_validation == "Based on Minimum Amount":
#             # Total taxable amount (excluding GST)
#             total_without_gst = flt(sum(d.base_net_amount for d in matching_items))

#             if total_without_gst >= flt(scheme.minimum_amount):
#                 discount_pct = flt(scheme.discount_percentage)
#                 apply_discount_to_invoice(doc, matching_items, discount_pct, scheme.name)

#         elif scheme.type_of_promo_validation == "Based on Minimum Quantity":
#             total_qty = sum(d.qty for d in matching_items)
#             if total_qty >= flt(scheme.minimum_quantity):
#                 free_qty = flt(scheme.free_quantity)
#                 add_free_items_to_invoice(doc, matching_items, free_qty, scheme.name)


# def apply_discount_to_invoice(doc, matching_items, discount_pct, scheme_name):
#     """Apply discount percentage to eligible items."""
#     for item in matching_items:
#         original_rate = flt(item.rate)
#         discount_amount = original_rate * (discount_pct / 100)
#         item.rate = original_rate - discount_amount
#         item.discount_percentage = discount_pct
#         item.promotional_scheme_applied = scheme_name

#     frappe.msgprint(f"✅ Promotional Scheme '{scheme_name}' applied with {discount_pct}% discount.")


# def add_free_items_to_invoice(doc, matching_items, free_qty, scheme_name):
#     """Add free quantity items to the invoice."""
#     for item in matching_items:
#         free_item = item.as_dict().copy()
#         free_item["qty"] = free_qty
#         free_item["rate"] = 0
#         free_item["amount"] = 0
#         free_item["promotional_scheme_applied"] = scheme_name
#         doc.append("items", free_item)

#     frappe.msgprint(f"🎁 Free Quantity ({free_qty}) added for scheme '{scheme_name}'.")
