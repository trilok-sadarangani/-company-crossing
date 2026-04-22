import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency
from config import COLOR_PRIMARY, COLOR_SEQUENCE, REVENUE_FIELD, VENDOR_COST_FIELD
from sidebar import render_filters

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
st.title("📊 Overview")
st.caption("High-level summary of revenue, bookings, and profit.")

df, _, _ = render_filters()
if df.empty:
    st.info("No data — check filters or Salesforce credentials.")
    st.stop()

rev_df = df[df[REVENUE_FIELD].notna()] if REVENUE_FIELD in df.columns else pd.DataFrame()

total_rev = rev_df[REVENUE_FIELD].sum() if not rev_df.empty else 0
total_cost = rev_df[VENDOR_COST_FIELD].fillna(0).sum() if VENDOR_COST_FIELD in rev_df.columns else 0
total_profit = total_rev - total_cost
avg_booking = rev_df[REVENUE_FIELD].mean() if not rev_df.empty else 0
total_trips = df["Trip__c"].nunique() if "Trip__c" in df.columns else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Revenue (£)", format_currency(total_rev))
c2.metric("Total Vendor Cost (£)", format_currency(total_cost))
c3.metric("Gross Profit (£)", format_currency(total_profit))
c4.metric("Avg Booking Value (£)", format_currency(avg_booking))
c5.metric("Unique Trips", f"{total_trips:,}")

st.markdown("---")

# ── Revenue trend ─────────────────────────────────────────────────────────────
st.subheader("Revenue Over Time")
if not rev_df.empty and "BookingMonth" in rev_df.columns:
    gran = st.radio("Group by", ["Month", "Quarter", "Year"], horizontal=True)
    period_col = {"Month": "BookingMonth", "Quarter": "BookingQuarter", "Year": "BookingYear"}[gran]

    trend = (
        rev_df.groupby(period_col)[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={period_col: "Period", REVENUE_FIELD: "Revenue"})
        .sort_values("Period")
    )
    trend["Label"] = trend["Revenue"].apply(format_currency)

    fig = px.area(
        trend, x="Period", y="Revenue",
        hover_data={"Label": True, "Revenue": False},
        labels={"Period": "", "Revenue": "Revenue (£)"},
        color_discrete_sequence=[COLOR_PRIMARY],
    )
    fig.update_layout(hovermode="x unified", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Not enough date data to show a trend.")

st.markdown("---")

# ── Booking type breakdown ────────────────────────────────────────────────────
st.subheader("Bookings by Type")
if "Category__c" in df.columns:
    cat = (
        df.groupby("Category__c")
        .agg(Bookings=("Id", "count"), Revenue=(REVENUE_FIELD, "sum"))
        .reset_index()
        .rename(columns={"Category__c": "Type"})
        .sort_values("Revenue", ascending=False)
    )
    cat["Revenue Label"] = cat["Revenue"].apply(format_currency)

    col_a, col_b = st.columns(2)
    with col_a:
        fig2 = px.bar(
            cat, x="Type", y="Bookings", title="Booking Count by Type",
            labels={"Type": "", "Bookings": "Bookings"},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig2.update_layout(xaxis_tickangle=-30, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        fig3 = px.pie(
            cat[cat["Revenue"] > 0], names="Type", values="Revenue",
            title="Revenue Share by Type", hole=0.4,
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── Trip status breakdown ─────────────────────────────────────────────────────
st.subheader("Trips by Status")
if "Trip_Status__c" in df.columns:
    # Deduplicate to one row per trip
    trips = df.drop_duplicates(subset="Trip__c")[["Trip__c", "Trip_Status__c"]].copy()
    status_counts = (
        trips.groupby("Trip_Status__c").size()
        .reset_index(name="Trips")
        .sort_values("Trips", ascending=False)
        .rename(columns={"Trip_Status__c": "Status"})
    )
    fig4 = px.bar(
        status_counts, x="Status", y="Trips",
        labels={"Status": "", "Trips": "Number of Trips"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig4.update_layout(xaxis_tickangle=-30, showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)
