"""
Tool definitions and data query functions for the Claude chat assistant.
Each tool returns a plain-text or JSON-serialisable string that Claude can
include verbatim in its answer.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from config import CONFIRMED_STATUSES, REVENUE_FIELD
from data_processor import _clean_clients, format_currency

# ── Tool schema definitions (passed to Claude) ────────────────────────────────

TOOLS = [
    {
        "name": "search_clients",
        "description": (
            "Search for clients by name (supports partial / fuzzy matches). "
            "Returns a list of matching client names so follow-up tools can use the exact name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name or partial name to search for",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_client_details",
        "description": (
            "Return full trip history, booking preferences, travel companions, "
            "and spending summary for a specific client. Use search_clients first "
            "if you are not certain of the exact name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {
                    "type": "string",
                    "description": "Exact canonical client name",
                }
            },
            "required": ["client_name"],
        },
    },
    {
        "name": "get_top_clients",
        "description": "Return the top clients ranked by total revenue / spend.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "How many clients to return (default 10)",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_business_summary",
        "description": (
            "Return high-level business metrics: total revenue, bookings, "
            "top destinations, top suppliers, and booking status breakdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ── Query helpers ─────────────────────────────────────────────────────────────


def _confirmed_bookings(bookings: pd.DataFrame) -> pd.DataFrame:
    if "Booking_Status__c" not in bookings.columns:
        return bookings
    return bookings[bookings["Booking_Status__c"].isin(CONFIRMED_STATUSES)]


def _fmt_date(ts) -> str:
    if pd.isna(ts):
        return "unknown date"
    try:
        return pd.Timestamp(ts).strftime("%d %b %Y")
    except Exception:
        return str(ts)


# ── Tool implementations ───────────────────────────────────────────────────────


def search_clients(query: str, trip_clients: pd.DataFrame) -> str:
    if trip_clients.empty or "Client_Name" not in trip_clients.columns:
        return "No client data available."

    clean = _clean_clients(trip_clients.copy())
    names = clean["Client_Name"].dropna().unique().tolist()
    q = query.lower()
    matches = [n for n in names if q in n.lower()]

    if not matches:
        # fallback: any word overlap
        words = q.split()
        matches = [n for n in names if any(w in n.lower() for w in words)]

    if not matches:
        return f"No clients found matching '{query}'."

    matches = sorted(set(matches))[:20]
    return "Matching clients:\n" + "\n".join(f"- {m}" for m in matches)


def get_client_details(
    client_name: str,
    trip_clients: pd.DataFrame,
    bookings: pd.DataFrame,
) -> str:
    if trip_clients.empty or bookings.empty:
        return "Data not available."

    clean = _clean_clients(trip_clients.copy())

    # Find trips for this client
    client_trips = clean[
        clean["Client_Name"].str.lower() == client_name.lower()
    ].copy()

    if client_trips.empty:
        # try partial match
        client_trips = clean[
            clean["Client_Name"].str.lower().str.contains(client_name.lower(), na=False)
        ].copy()

    if client_trips.empty:
        return f"No records found for client '{client_name}'."

    canonical_name = client_trips["Client_Name"].iloc[0]
    trip_ids = client_trips["Trip__c"].dropna().unique().tolist()

    # Confirmed bookings for those trips
    conf = _confirmed_bookings(bookings)
    client_bookings = conf[conf["Trip__c"].isin(trip_ids)].copy()

    lines = [f"## {canonical_name}"]

    # ── Trip history ──────────────────────────────────────────────────────────
    trip_summary_rows = []
    for trip_id in trip_ids:
        tb = client_bookings[client_bookings["Trip__c"] == trip_id]
        trip_row = client_trips[client_trips["Trip__c"] == trip_id].iloc[0]
        trip_name = trip_row.get("Trip_Name", trip_id) if "Trip_Name" in trip_row else trip_id
        start = _fmt_date(tb["Date_from__c"].min() if not tb.empty else None)
        end = _fmt_date(tb["Date_to__c"].max() if not tb.empty and "Date_to__c" in tb.columns else None)
        revenue = tb[REVENUE_FIELD].sum() if REVENUE_FIELD in tb.columns else 0
        destinations = (
            tb["Destination"].dropna().unique().tolist()
            if "Destination" in tb.columns else []
        )
        suppliers = (
            tb["Supplier_Name"].dropna().unique().tolist()
            if "Supplier_Name" in tb.columns else []
        )
        categories = (
            tb["Category__c"].dropna().value_counts().index.tolist()
            if "Category__c" in tb.columns else []
        )
        trip_summary_rows.append({
            "trip_id": trip_id,
            "trip_name": trip_name,
            "start": start,
            "revenue": revenue,
            "destinations": destinations,
            "suppliers": suppliers,
            "categories": categories,
        })

    # Sort trips by start date descending
    def _sort_key(r):
        tb = client_bookings[client_bookings["Trip__c"] == r["trip_id"]]
        if tb.empty or "Date_from__c" not in tb.columns:
            return pd.Timestamp.min.tz_localize("UTC")
        mn = tb["Date_from__c"].min()
        return mn if not pd.isna(mn) else pd.Timestamp.min.tz_localize("UTC")

    trip_summary_rows.sort(key=_sort_key, reverse=True)

    lines.append(f"\n### Trip History ({len(trip_summary_rows)} trips)")
    for r in trip_summary_rows:
        dest_str = ", ".join(r["destinations"]) if r["destinations"] else "unknown destination"
        lines.append(
            f"- **{r['trip_name']}** | {r['start']} | {dest_str} | {format_currency(r['revenue'])}"
        )
        if r["suppliers"]:
            lines.append(f"  Suppliers: {', '.join(r['suppliers'][:5])}")
        if r["categories"]:
            lines.append(f"  Categories: {', '.join(r['categories'][:5])}")

    # ── Most recent trip detail ───────────────────────────────────────────────
    if trip_summary_rows:
        latest = trip_summary_rows[0]
        tb = client_bookings[client_bookings["Trip__c"] == latest["trip_id"]]
        if not tb.empty and "Date_from__c" in tb.columns:
            last_date = tb["Date_from__c"].max()
            now = pd.Timestamp.now(tz="UTC")
            days_ago = (now - last_date).days if not pd.isna(last_date) else None
            if days_ago is not None:
                lines.append(
                    f"\n### Last Trip\n"
                    f"{_fmt_date(last_date)} ({days_ago} days ago) — "
                    f"{', '.join(latest['destinations']) or 'destination unknown'}"
                )

    # ── Preferences (most booked categories & suppliers across all trips) ─────
    if not client_bookings.empty:
        lines.append("\n### Preferences")
        if "Category__c" in client_bookings.columns:
            top_cats = (
                client_bookings["Category__c"].value_counts().head(5)
            )
            lines.append("**Most booked categories:**")
            for cat, cnt in top_cats.items():
                lines.append(f"  - {cat}: {cnt} booking(s)")

        if "Supplier_Name" in client_bookings.columns:
            top_sup = (
                client_bookings["Supplier_Name"].dropna().value_counts().head(5)
            )
            lines.append("**Favourite suppliers:**")
            for sup, cnt in top_sup.items():
                lines.append(f"  - {sup}: {cnt} booking(s)")

        if "Destination" in client_bookings.columns:
            top_dest = (
                client_bookings["Destination"].dropna().value_counts().head(5)
            )
            lines.append("**Top destinations:**")
            for dest, cnt in top_dest.items():
                lines.append(f"  - {dest}: {cnt} booking(s)")

    # ── Travel companions ─────────────────────────────────────────────────────
    companion_ids = set(trip_ids)
    # All clients who share any of these trips
    companions_df = clean[
        clean["Trip__c"].isin(companion_ids) &
        (clean["Client_Name"].str.lower() != canonical_name.lower())
    ]
    companion_names = companions_df["Client_Name"].dropna().unique().tolist()

    if companion_names:
        lines.append("\n### Travel Companions")
        for name in sorted(set(companion_names))[:10]:
            shared = companions_df[companions_df["Client_Name"] == name]["Trip__c"].nunique()
            lines.append(f"  - {name} ({shared} shared trip(s))")
    else:
        lines.append("\n### Travel Companions\nNo shared trips found with other clients.")

    # ── Spend summary ─────────────────────────────────────────────────────────
    if not client_bookings.empty and REVENUE_FIELD in client_bookings.columns:
        total = client_bookings[REVENUE_FIELD].sum()
        lines.append(f"\n### Spend Summary\nTotal confirmed spend: {format_currency(total)}")

    return "\n".join(lines)


def get_top_clients(
    limit: int,
    trip_clients: pd.DataFrame,
    bookings: pd.DataFrame,
) -> str:
    if trip_clients.empty or bookings.empty:
        return "Data not available."

    clean = _clean_clients(trip_clients.copy())
    conf = _confirmed_bookings(bookings)

    if REVENUE_FIELD not in conf.columns:
        return "Revenue field not available."

    merged = clean.merge(
        conf[["Trip__c", REVENUE_FIELD]], on="Trip__c", how="inner"
    )
    if merged.empty:
        return "No confirmed bookings with revenue data."

    top = (
        merged.groupby("Client_Name")[REVENUE_FIELD]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

    lines = [f"## Top {limit} Clients by Total Spend"]
    for i, (name, rev) in enumerate(top.items(), 1):
        lines.append(f"{i}. {name} — {format_currency(rev)}")
    return "\n".join(lines)


def get_business_summary(
    bookings: pd.DataFrame,
    trip_clients: pd.DataFrame,
) -> str:
    if bookings.empty:
        return "No booking data available."

    conf = _confirmed_bookings(bookings)
    total_rev = conf[REVENUE_FIELD].sum() if REVENUE_FIELD in conf.columns else 0
    total_bookings = len(conf)
    total_trips = conf["Trip__c"].nunique() if "Trip__c" in conf.columns else 0

    lines = ["## Business Summary"]
    lines.append(f"- Confirmed bookings: {total_bookings:,}")
    lines.append(f"- Confirmed trips: {total_trips:,}")
    lines.append(f"- Total revenue: {format_currency(total_rev)}")

    if "Destination" in conf.columns:
        top_dest = conf["Destination"].dropna().value_counts().head(5)
        lines.append("\n**Top destinations:**")
        for d, c in top_dest.items():
            lines.append(f"  - {d}: {c} booking(s)")

    if "Supplier_Name" in conf.columns:
        top_sup = conf["Supplier_Name"].dropna().value_counts().head(5)
        lines.append("\n**Top suppliers:**")
        for s, c in top_sup.items():
            lines.append(f"  - {s}: {c} booking(s)")

    if "Category__c" in conf.columns:
        cat_counts = conf["Category__c"].dropna().value_counts().head(5)
        lines.append("\n**Booking categories:**")
        for cat, c in cat_counts.items():
            lines.append(f"  - {cat}: {c}")

    if not trip_clients.empty and "Client_Name" in trip_clients.columns:
        clean = _clean_clients(trip_clients.copy())
        n_clients = clean["Client_Name"].nunique()
        lines.append(f"\n- Unique clients: {n_clients:,}")

    return "\n".join(lines)


# ── Dispatcher ────────────────────────────────────────────────────────────────


def execute_tool(
    name: str,
    tool_input: dict,
    bookings: pd.DataFrame,
    trip_clients: pd.DataFrame,
) -> str:
    try:
        if name == "search_clients":
            return search_clients(tool_input["query"], trip_clients)
        if name == "get_client_details":
            return get_client_details(tool_input["client_name"], trip_clients, bookings)
        if name == "get_top_clients":
            limit = int(tool_input.get("limit", 10))
            return get_top_clients(limit, trip_clients, bookings)
        if name == "get_business_summary":
            return get_business_summary(bookings, trip_clients)
        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"
