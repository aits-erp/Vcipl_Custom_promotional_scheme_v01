# File: promotional_scheme/report/custom_promotional_scheme_report/custom_promotional_scheme_report.py
import frappe
from frappe.utils import nowdate, flt, getdate

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": "Scheme Name", "fieldname": "scheme_name", "fieldtype": "Data", "width": 180},
        {"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 120},
        {"label": "Party", "fieldname": "party_name", "fieldtype": "Data", "width": 160},
        {"label": "Apply On", "fieldname": "apply_on", "fieldtype": "Data", "width": 100},
        {"label": "Item / Item Group", "fieldname": "item_or_group", "fieldtype": "Data", "width": 180},
        {"label": "Minimum Amount", "fieldname": "minimum_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Minimum Quantity", "fieldname": "minimum_quantity", "fieldtype": "Float", "width": 120},
        {"label": "Discount %", "fieldname": "discount_percentage", "fieldtype": "Percent", "width": 100},
        {"label": "Free Quantity", "fieldname": "free_quantity", "fieldtype": "Float", "width": 100},
        {"label": "Valid From", "fieldname": "valid_from", "fieldtype": "Date", "width": 110},
        {"label": "Valid To", "fieldname": "valid_to", "fieldtype": "Date", "width": 110},
        {"label": "Total Invoice Amount", "fieldname": "invoice_amount", "fieldtype": "Currency", "width": 130},
        {"label": "Total Quantity", "fieldname": "invoice_qty", "fieldtype": "Float", "width": 110},
        {"label": "Eligibility Status", "fieldname": "eligibility_status", "fieldtype": "Data", "width": 140},
    ]

# -------------------------
# Helpers: extract values from scheme doc
# (self-contained so report doesn't rely on other modules)
# -------------------------
def _extract_values_from_child_rows(doc, fieldname, possible_keys=None):
    vals = set()
    possible_keys = possible_keys or []
    rows = doc.get(fieldname) or []
    # If rows is a simple list of strings
    if isinstance(rows, list) and rows and isinstance(rows[0], str):
        for v in rows:
            if v:
                vals.add(str(v))
        return vals

    for row in rows:
        # row might be Document or dict
        row_dict = row.as_dict() if hasattr(row, "as_dict") else dict(row)
        for k in possible_keys:
            if k in row_dict and row_dict.get(k):
                vals.add(str(row_dict.get(k)))
                break
        else:
            # fallback: first non-meta non-empty value
            for k2, v2 in row_dict.items():
                if k2 in ("idx", "name", "parent", "parentfield", "parenttype", "doctype"):
                    continue
                if v2:
                    vals.add(str(v2))
                    break
    return vals

def _extract_item_codes_from_scheme(scheme_doc):
    item_codes = set()
    # Item codes table (child)
    try:
        item_code_vals = _extract_values_from_child_rows(scheme_doc, "promotional_scheme_on_item_code", possible_keys=["item_code", "item"])
        item_codes.update(item_code_vals)
    except Exception:
        pass

    # Item groups -> expand to item codes
    try:
        item_group_vals = _extract_values_from_child_rows(scheme_doc, "promotional_scheme_on_item_group", possible_keys=["item_group", "group"])
        if item_group_vals:
            items = frappe.get_all("Item", filters={"item_group": ["in", list(item_group_vals)]}, pluck="name") or []
            item_codes.update(items)
    except Exception:
        pass

    # normalize
    return set([str(i) for i in item_codes if i])

def _extract_party_values_from_scheme(scheme_doc):
    customers = _extract_values_from_child_rows(scheme_doc, "customer", possible_keys=["customer", "value"])
    customer_groups = _extract_values_from_child_rows(scheme_doc, "customer_group", possible_keys=["customer_group", "group"])
    territories = _extract_values_from_child_rows(scheme_doc, "territory", possible_keys=["territory", "value"])
    suppliers = _extract_values_from_child_rows(scheme_doc, "supplier", possible_keys=["supplier", "value"])
    supplier_groups = _extract_values_from_child_rows(scheme_doc, "supplier_group", possible_keys=["supplier_group", "group"])

    # Expand customer groups -> customers
    if customer_groups:
        cg_customers = frappe.get_all("Customer", filters={"customer_group": ["in", list(customer_groups)]}, pluck="name") or []
        customers.update([str(c) for c in cg_customers if c])

    # Expand territories -> customers
    if territories:
        t_customers = frappe.get_all("Customer", filters={"territory": ["in", list(territories)]}, pluck="name") or []
        customers.update([str(c) for c in t_customers if c])

    # Expand supplier groups -> suppliers
    if supplier_groups:
        sg_suppliers = frappe.get_all("Supplier", filters={"supplier_group": ["in", list(supplier_groups)]}, pluck="name") or []
        suppliers.update([str(s) for s in sg_suppliers if s])

    return {
        "customers": set([str(c) for c in customers if c]),
        "customer_groups": set([str(cg) for cg in customer_groups if cg]),
        "territories": set([str(t) for t in territories if t]),
        "suppliers": set([str(s) for s in suppliers if s]),
        "supplier_groups": set([str(sg) for sg in supplier_groups if sg]),
    }

# -------------------------
# Main data builder
# -------------------------

# def get_data(filters):
#     # Filter schemes first (supports scheme_name, apply_on, from_date, to_date)
#     sql_where = ["1=1"]
#     params = {}

#     if filters.get("scheme_name"):
#         sql_where.append("name = %(scheme_name)s")
#         params["scheme_name"] = filters.get("scheme_name")

#     if filters.get("apply_on"):
#         sql_where.append("apply_on = %(apply_on)s")
#         params["apply_on"] = filters.get("apply_on")

#     # Note: we don't limit by valid_from/valid_to here because we will use per-scheme date window
#     schemes = frappe.db.sql(
#         f"""SELECT name FROM `tabCustom Promotional Scheme` WHERE {" AND ".join(sql_where)} ORDER BY creation DESC""",
#         params, as_dict=True
#     ) or []

#     result_rows = []

#     for s in schemes:
#         try:
#             scheme_doc = frappe.get_doc("Custom Promotional Scheme", s.name)
#         except Exception:
#             continue

#         # Expand parties and items
#         parties_dict = _extract_party_values_from_scheme(scheme_doc)
#         # Build explicit party list (list of tuples (party_type, party_name))
#         parties = []
#         party_side = (scheme_doc.select_the_party or "").strip()  # "Selling" or "Buying" expected

#         if party_side == "Selling":
#             # customers set may be empty -> treat as all
#             if parties_dict["customers"]:
#                 for c in sorted(parties_dict["customers"]):
#                     parties.append(("Customer", c))
#             else:
#                 parties = [("Customer", None)]  # None indicates All customers
#         elif party_side == "Buying":
#             if parties_dict["suppliers"]:
#                 for sname in sorted(parties_dict["suppliers"]):
#                     parties.append(("Supplier", sname))
#             else:
#                 parties = [("Supplier", None)]
#         else:
#             # If not set, default to Selling + All
#             parties = [("Customer", None)]
#             party_side = "Selling"

#         # Items
#         item_codes = _extract_item_codes_from_scheme(scheme_doc)
#         # If apply_on is Item Group but there are no groups/items specified -> treat as All
#         if item_codes:
#             items = sorted(item_codes)
#         else:
#             items = [None]  # None indicates All Items

#         # Date window: report-level filters override scheme dates
#         report_from = filters.get("from_date") or None
#         report_to = filters.get("to_date") or None

#         # We'll run a grouped SQL to fetch totals for this scheme in one shot:
#         totals_map = _get_totals_for_scheme(scheme_doc, party_side, parties, items, report_from, report_to)

#         # Now create rows: cartesian product parties × items
#         for party_type, party_name in parties:
#             for item_code in items:
#                 key = (str(party_name) if party_name else None, str(item_code) if item_code else None)
#                 totals = totals_map.get(key, {"total_amount": 0.0, "total_qty": 0.0})
#                 total_amount = flt(totals.get("total_amount") or 0.0)
#                 total_qty = flt(totals.get("total_qty") or 0.0)

#                 # Eligibility check based on scheme's validation
#                 validation_type = (scheme_doc.type_of_promo_validation or "").strip()
#                 eligible = False
#                 if validation_type == "Based on Minimum Amount":
#                     min_amount = flt(getattr(scheme_doc, "minimum_amount", 0) or 0)
#                     if min_amount > 0 and total_amount >= min_amount:
#                         eligible = True
#                 elif validation_type == "Based on Minimum Quantity":
#                     min_qty = flt(getattr(scheme_doc, "minimum_quantity", 0) or 0)
#                     if min_qty > 0 and total_qty >= min_qty:
#                         eligible = True
#                 else:
#                     # If no validation type, treat as eligible if any activity
#                     eligible = bool(total_amount > 0 or total_qty > 0)

#                 # item_or_group column: if scheme apply_on Item Group but we expanded to item codes,
#                 # show the concrete item_code; otherwise show '-' when None
#                 item_or_group_display = item_code if item_code else "-"

#                 result_rows.append({
#                     "scheme_name": scheme_doc.scheme_name or scheme_doc.name,
#                     "party_type": party_type,
#                     "party_name": party_name or "All",
#                     "apply_on": scheme_doc.apply_on or "-",
#                     "item_or_group": item_or_group_display,
#                     "minimum_amount": flt(getattr(scheme_doc, "minimum_amount", 0) or 0),
#                     "minimum_quantity": flt(getattr(scheme_doc, "minimum_quantity", 0) or 0),
#                     "discount_percentage": flt(getattr(scheme_doc, "discount_percentage", 0) or 0),
#                     "free_quantity": flt(getattr(scheme_doc, "free_quantity", 0) or 0),
#                     "valid_from": getattr(scheme_doc, "valid_from", None),
#                     "valid_to": getattr(scheme_doc, "valid_to", None),
#                     "invoice_amount": total_amount,
#                     "invoice_qty": total_qty,
#                     "eligibility_status": "Eligible" if eligible else "Not Eligible",
#                 })
#     # after result_rows populated
#     result_rows = _apply_report_filters(result_rows, filters or {})

#     # (If you still want only eligible rows always, keep your eligible filter:)
#     # eligible_rows = [row for row in result_rows if row.get("eligibility_status") == "Eligible"]
#     # return eligible_rows

#     # If you want the report to obey the 'Show Only Eligible' checkbox above, use:
#     return result_rows


#     #return result_rows
#         # ✅ Keep only rows where eligibility_status is "Eligible"
#     # eligible_rows = [row for row in result_rows if row.get("eligibility_status") == "Eligible"]

#     # return eligible_rows


# -------------------------
# Apply report filters to result_rows (call this before returning)
# -------------------------
def _apply_report_filters(result_rows, filters):
    rows = result_rows

    # simple equality filters
    if filters.get("scheme_name"):
        rows = [r for r in rows if (r.get("scheme_name") or "").strip() == filters.get("scheme_name")]

    if filters.get("party_type"):
        rows = [r for r in rows if (r.get("party_type") or "").strip() == filters.get("party_type")]

    if filters.get("party_name"):
        # party_name may be "All" for all customers; do an exact match with provided party link
        rows = [r for r in rows if (r.get("party_name") or "") == filters.get("party_name")]

    if filters.get("apply_on"):
        rows = [r for r in rows if (r.get("apply_on") or "") == filters.get("apply_on")]

    # partial-match for item_or_group (user may type part of item code / group)
    if filters.get("item_or_group"):
        term = str(filters.get("item_or_group")).strip().lower()
        rows = [r for r in rows if (r.get("item_or_group") or "").lower().find(term) != -1]

    # Date filters (these refer to scheme validity window columns already present in row)
    # If user supplied from_date/to_date filter, ensure scheme validity intersects requested window
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    if from_date:
        from_date = getdate(from_date)
        rows = [r for r in rows if not r.get("valid_to") or getdate(r.get("valid_to")) >= from_date]
    if to_date:
        to_date = getdate(to_date)
        rows = [r for r in rows if not r.get("valid_from") or getdate(r.get("valid_from")) <= to_date]

    # Numeric ranges on invoice totals
    if filters.get("min_invoice_amount") is not None:
        rows = [r for r in rows if flt(r.get("invoice_amount") or 0) >= flt(filters.get("min_invoice_amount"))]
    if filters.get("max_invoice_amount") is not None:
        rows = [r for r in rows if flt(r.get("invoice_amount") or 0) <= flt(filters.get("max_invoice_amount"))]

    if filters.get("min_invoice_qty") is not None:
        rows = [r for r in rows if flt(r.get("invoice_qty") or 0) >= flt(filters.get("min_invoice_qty"))]
    if filters.get("max_invoice_qty") is not None:
        rows = [r for r in rows if flt(r.get("invoice_qty") or 0) <= flt(filters.get("max_invoice_qty"))]

    # Discount percentage ranges (based on scheme field discount_percentage)
    if filters.get("discount_min") is not None:
        rows = [r for r in rows if flt(r.get("discount_percentage") or 0) >= flt(filters.get("discount_min"))]
    if filters.get("discount_max") is not None:
        rows = [r for r in rows if flt(r.get("discount_percentage") or 0) <= flt(filters.get("discount_max"))]

    # show_only_eligible toggle (JS default is 1)
    if filters.get("show_only_eligible") in (1, "1", True, "True", "true"):
        rows = [r for r in rows if (r.get("eligibility_status") or "").lower() == "eligible"]

    return rows

# -------------------------
# SQL helper to get totals for a scheme (single grouped query per scheme & side)
# parties: list of tuples (party_type, party_name) where party_name may be None meaning All
# items: list of item_codes or [None] meaning All
# -------------------------
# def _get_totals_for_scheme(scheme_doc, party_side, parties, items, report_from=None, report_to=None):
#     """
#     Returns dict keyed by (party_name or None, item_code or None) -> { total_amount, total_qty }
#     """
#     # Normalize date range
#     if report_from:
#         from_date = getdate(report_from)
#     else:
#         from_date = getdate(getattr(scheme_doc, "valid_from", None)) if getattr(scheme_doc, "valid_from", None) else None

#     if report_to:
#         to_date = getdate(report_to)
#     else:
#         to_date = getdate(getattr(scheme_doc, "valid_to", None)) if getattr(scheme_doc, "valid_to", None) else None

#     # Build party list values (only concrete names, ignore 'All' marker)
#     concrete_parties = [pname for (ptype, pname) in parties if pname]
#     # For SQL we need lists of parties separated by Customer/Supplier depending on side.
#     # Items concrete list:
#     concrete_items = [i for i in items if i]

#     params = []
#     where_clauses = ["si.docstatus = 1"]

#     # date filter
#     if from_date and to_date:
#         where_clauses.append("si.posting_date BETWEEN %s AND %s")
#         params.extend([str(from_date), str(to_date)])
#     elif from_date:
#         where_clauses.append("si.posting_date >= %s")
#         params.append(str(from_date))
#     elif to_date:
#         where_clauses.append("si.posting_date <= %s")
#         params.append(str(to_date))

#     # party filter (if concrete parties provided) - build OR block
#     party_ors = []
#     if party_side == "Selling":
#         if concrete_parties:
#             placeholders = ", ".join(["%s"] * len(concrete_parties))
#             party_ors.append(f"si.customer IN ({placeholders})")
#             params.extend(concrete_parties)
#     else:
#         if concrete_parties:
#             placeholders = ", ".join(["%s"] * len(concrete_parties))
#             party_ors.append(f"si.supplier IN ({placeholders})")
#             params.extend(concrete_parties)

#     if party_ors:
#         where_clauses.append("(" + " OR ".join(party_ors) + ")")

#     # item filter - will be appended to SQL separately
#     item_clause = ""
#     if concrete_items:
#         placeholders = ", ".join(["%s"] * len(concrete_items))
#         item_clause = f" AND sii.item_code IN ({placeholders})"

#     # Decide table names
#     if party_side == "Selling":
#         header = "`tabSales Invoice`"
#         item_table = "`tabSales Invoice Item`"
#         party_col = "si.customer"
#     else:
#         header = "`tabPurchase Invoice`"
#         item_table = "`tabPurchase Invoice Item`"
#         party_col = "si.supplier"

#     sql = f"""
#         SELECT
#            {party_col} AS party_name,
#            sii.item_code AS item_code,
#            SUM(COALESCE(sii.base_net_amount, sii.base_amount, sii.amount, 0)) AS total_amount,
#            SUM(COALESCE(sii.qty, 0)) AS total_qty
#         FROM {header} si
#         JOIN {item_table} sii ON sii.parent = si.name
#         WHERE {" AND ".join(where_clauses)}
#         {item_clause}
#         GROUP BY {party_col}, sii.item_code
#     """

#     final_params = list(params)
#     if concrete_items:
#         final_params.extend(concrete_items)

#     rows = frappe.db.sql(sql, tuple(final_params), as_dict=True) or []

#     # Map to dict keyed by (party_name or None, item_code or None)
#     totals_map = {}
#     for r in rows:
#         p = r.get("party_name") or None
#         item = r.get("item_code") or None
#         totals_map[(p, item)] = {
#             "total_amount": flt(r.get("total_amount") or 0.0),
#             "total_qty": flt(r.get("total_qty") or 0.0)
#         }

#     return totals_map


def _get_totals_for_scheme(scheme_doc, party_side, parties, items, report_from=None, report_to=None):
    """
    Returns dict keyed by (party_name or None, item_code or None) -> { total_amount, total_qty }
    Enhanced: if no concrete parties given, apply scheme to ALL parties of that side (Selling/Buying)
    """
    # Normalize date range
    if report_from:
        from_date = getdate(report_from)
    else:
        from_date = getdate(getattr(scheme_doc, "valid_from", None)) if getattr(scheme_doc, "valid_from", None) else None

    if report_to:
        to_date = getdate(report_to)
    else:
        to_date = getdate(getattr(scheme_doc, "valid_to", None)) if getattr(scheme_doc, "valid_to", None) else None

    # Build party list values (only concrete names, ignore 'All' marker)
    concrete_parties = [pname for (ptype, pname) in parties if pname]
    concrete_items = [i for i in items if i]

    params = []
    where_clauses = ["si.docstatus = 1"]

    # --- Date filter ---
    if from_date and to_date:
        where_clauses.append("si.posting_date BETWEEN %s AND %s")
        params.extend([str(from_date), str(to_date)])
    elif from_date:
        where_clauses.append("si.posting_date >= %s")
        params.append(str(from_date))
    elif to_date:
        where_clauses.append("si.posting_date <= %s")
        params.append(str(to_date))

    # --- Party filter logic ---
    # If no specific parties defined, we apply to ALL customers/suppliers automatically
    if party_side == "Selling":
        party_col = "si.customer"
        header = "`tabSales Invoice`"
        item_table = "`tabSales Invoice Item`"
    else:
        party_col = "si.supplier"
        header = "`tabPurchase Invoice`"
        item_table = "`tabPurchase Invoice Item`"

    if concrete_parties:
        placeholders = ", ".join(["%s"] * len(concrete_parties))
        where_clauses.append(f"{party_col} IN ({placeholders})")
        params.extend(concrete_parties)
    else:
        # No party specified in scheme → apply to all customers/suppliers of that side
        # (no party filter needed here)
        pass

    # --- Item filter ---
    item_clause = ""
    if concrete_items:
        placeholders = ", ".join(["%s"] * len(concrete_items))
        item_clause = f" AND sii.item_code IN ({placeholders})"

    # --- Final SQL ---
    sql = f"""
        SELECT
            {party_col} AS party_name,
            sii.item_code AS item_code,
            SUM(COALESCE(sii.base_net_amount, sii.base_amount, sii.amount, 0)) AS total_amount,
            SUM(COALESCE(sii.qty, 0)) AS total_qty
        FROM {header} si
        JOIN {item_table} sii ON sii.parent = si.name
        WHERE {" AND ".join(where_clauses)}
        {item_clause}
        GROUP BY {party_col}, sii.item_code
    """

    final_params = list(params)
    if concrete_items:
        final_params.extend(concrete_items)

    rows = frappe.db.sql(sql, tuple(final_params), as_dict=True) or []

    totals_map = {}
    for r in rows:
        p = r.get("party_name") or None
        item = r.get("item_code") or None
        totals_map[(p, item)] = {
            "total_amount": flt(r.get("total_amount") or 0.0),
            "total_qty": flt(r.get("total_qty") or 0.0)
        }

    return totals_map


def get_data(filters):
    # Filter schemes first (supports scheme_name, apply_on, from_date, to_date)
    sql_where = ["1=1"]
    params = {}

    if filters.get("scheme_name"):
        sql_where.append("name = %(scheme_name)s")
        params["scheme_name"] = filters.get("scheme_name")

    if filters.get("apply_on"):
        sql_where.append("apply_on = %(apply_on)s")
        params["apply_on"] = filters.get("apply_on")

    schemes = frappe.db.sql(
        f"""SELECT name FROM `tabCustom Promotional Scheme`
            WHERE {" AND ".join(sql_where)} ORDER BY creation DESC""",
        params, as_dict=True
    ) or []

    result_rows = []

    for s in schemes:
        try:
            scheme_doc = frappe.get_doc("Custom Promotional Scheme", s.name)
        except Exception:
            continue

        parties_dict = _extract_party_values_from_scheme(scheme_doc)
        parties = []
        party_side = (scheme_doc.select_the_party or "").strip()  # "Selling" or "Buying"

        if party_side == "Selling":
            if parties_dict["customers"]:
                for c in sorted(parties_dict["customers"]):
                    parties.append(("Customer", c))
            else:
                parties = []  # none means apply to all
        elif party_side == "Buying":
            if parties_dict["suppliers"]:
                for sname in sorted(parties_dict["suppliers"]):
                    parties.append(("Supplier", sname))
            else:
                parties = []
        else:
            party_side = "Selling"
            parties = []

        # Items
        item_codes = _extract_item_codes_from_scheme(scheme_doc)
        items = sorted(item_codes) if item_codes else [None]

        report_from = filters.get("from_date") or None
        report_to = filters.get("to_date") or None

        totals_map = _get_totals_for_scheme(scheme_doc, party_side, parties, items, report_from, report_to)

        # Build result rows
        all_parties = set([p for (p, _) in totals_map.keys() if p]) or set()
        all_items = set([i for (_, i) in totals_map.keys() if i]) or set()

        # When no specific parties defined, use all found in totals_map
        if not parties:
            if party_side == "Selling":
                parties = [("Customer", p) for p in all_parties]
            else:
                parties = [("Supplier", p) for p in all_parties]

        for party_type, party_name in parties:
            for item_code in items:
                key = (party_name, item_code)
                totals = totals_map.get(key, {"total_amount": 0.0, "total_qty": 0.0})
                total_amount = flt(totals.get("total_amount") or 0.0)
                total_qty = flt(totals.get("total_qty") or 0.0)

                validation_type = (scheme_doc.type_of_promo_validation or "").strip()
                eligible = False
                if validation_type == "Based on Minimum Amount":
                    min_amount = flt(getattr(scheme_doc, "minimum_amount", 0) or 0)
                    if min_amount > 0 and total_amount >= min_amount:
                        eligible = True
                elif validation_type == "Based on Minimum Quantity":
                    min_qty = flt(getattr(scheme_doc, "minimum_quantity", 0) or 0)
                    if min_qty > 0 and total_qty >= min_qty:
                        eligible = True
                else:
                    eligible = bool(total_amount > 0 or total_qty > 0)

                item_or_group_display = item_code if item_code else "-"

                result_rows.append({
                    "scheme_name": scheme_doc.scheme_name or scheme_doc.name,
                    "party_type": party_type,
                    "party_name": party_name or "All",
                    "apply_on": scheme_doc.apply_on or "-",
                    "item_or_group": item_or_group_display,
                    "minimum_amount": flt(getattr(scheme_doc, "minimum_amount", 0) or 0),
                    "minimum_quantity": flt(getattr(scheme_doc, "minimum_quantity", 0) or 0),
                    "discount_percentage": flt(getattr(scheme_doc, "discount_percentage", 0) or 0),
                    "free_quantity": flt(getattr(scheme_doc, "free_quantity", 0) or 0),
                    "valid_from": getattr(scheme_doc, "valid_from", None),
                    "valid_to": getattr(scheme_doc, "valid_to", None),
                    "invoice_amount": total_amount,
                    "invoice_qty": total_qty,
                    "eligibility_status": "Eligible" if eligible else "Not Eligible",
                })

    result_rows = _apply_report_filters(result_rows, filters or {})
    return result_rows
