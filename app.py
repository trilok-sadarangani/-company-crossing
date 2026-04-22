import streamlit as st
import pandas as pd
from config import PAGE_TITLE, PAGE_ICON, LAYOUT, REVENUE_FIELD
from sidebar import render_filters
from data_processor import format_currency

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

st.title("✈️ Company Crossing — Travel Analytics")
st.caption("Live data from Salesforce · Refreshes every 5 minutes")

filtered_df, df_all, trip_clients = render_filters()

if filtered_df.empty and df_all.empty:
    st.warning(
        "No booking data loaded. "
        "Make sure your `.env` file has valid Salesforce credentials."
    )
    st.stop()

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
