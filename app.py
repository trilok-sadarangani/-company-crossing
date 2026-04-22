import streamlit as st
import pandas as pd
from config import PAGE_TITLE, PAGE_ICON, LAYOUT, REVENUE_FIELD, CONFIRMED_STATUSES
from salesforce_client import load_bookings, load_trip_clients
from data_processor import enrich, apply_filters, confirmed, format_currency

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

st.title("✈️ Company Crossing — Travel Analytics")
st.caption("Live data from Salesforce · Refreshes every 5 minutes")

# ── Load data ────────────────────────────────────────────────────────────────
bookings_raw = load_bookings()
trip_clients = load_trip_clients()

if bookings_raw.empty:
    st.warning(
        "No booking data loaded. "
        "Make sure your `.env` file has valid Salesforce credentials."
    )
    st.stop()

df = enrich(bookings_raw)

# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.header("Filters")
st.sidebar.caption("Apply to all pages.")

valid_dates = df["Date_from__c"].dropna()
min_date = valid_dates.min().date() if not valid_dates.empty else pd.Timestamp("2020-01-01").date()
max_date = valid_dates.max().date() if not valid_dates.empty else pd.Timestamp.today().date()

start_date = st.sidebar.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

all_categories = sorted(df["Category__c"].dropna().unique().tolist()) if "Category__c" in df.columns else []
selected_categories = st.sidebar.multiselect(
    "Booking Type", options=all_categories, default=all_categories,
    help="Filter by type of service booked"
)

all_statuses = sorted(df["Booking_Status__c"].dropna().unique().tolist()) if "Booking_Status__c" in df.columns else []
selected_statuses = st.sidebar.multiselect(
    "Booking Status", options=all_statuses, default=CONFIRMED_STATUSES,
    help="Confirmed = active/completed bookings. Cancelled bookings are hidden by default — add them back here if needed."
)

filtered_df = apply_filters(df, start_date, end_date, selected_categories, selected_statuses)

# Undated trips note
if "Date_from__c" in df.columns:
    undated = df["Date_from__c"].isna().sum()
    if undated > 0:
        st.sidebar.info(f"{undated:,} bookings have no date and are excluded from time-based charts.")

# Share via session state
st.session_state["df"] = filtered_df
st.session_state["df_all"] = df
st.session_state["trip_clients"] = trip_clients

# ── Home KPIs ────────────────────────────────────────────────────────────────
rev_df = filtered_df[filtered_df[REVENUE_FIELD].notna()] if REVENUE_FIELD in filtered_df.columns else filtered_df

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Bookings", f"{len(filtered_df):,}")
c2.metric("Bookings with Revenue", f"{len(rev_df):,}")
c3.metric("Total Revenue (GBP)", format_currency(rev_df[REVENUE_FIELD].sum()) if not rev_df.empty else "£0")
c4.metric("Unique Trips", f"{filtered_df['Trip__c'].nunique():,}" if "Trip__c" in filtered_df.columns else "—")
c5.metric("Unique Clients", f"{trip_clients['Client__c'].nunique():,}" if not trip_clients.empty else "—")

st.markdown("---")
st.markdown(
    "Use the **sidebar navigation** to explore detailed analytics."
)
st.markdown("""
| Page | What you'll find |
|---|---|
| Overview | Revenue trend and booking type breakdown |
| Revenue Analysis | Revenue by destination, supplier, and period |
| Customer Insights | Top clients, where they come from, repeat travel |
| Vacation Patterns | Seasonal trends, destinations, trip durations |
| Performance | Best/worst destinations, suppliers, and agents |
""")
