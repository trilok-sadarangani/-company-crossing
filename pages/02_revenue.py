import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency
from config import COLOR_SEQUENCE, REVENUE_FIELD, VENDOR_COST_FIELD

st.set_page_config(page_title="Revenue Analysis", page_icon="💰", layout="wide")
st.title("💰 Revenue Analysis")
st.caption("Where your money comes from — by destination, supplier, and period.")

df = st.session_state.get("df", pd.DataFrame())
if df.empty:
    st.warning("No data — return to the Home page first.")
    st.stop()

rev_df = df[df[REVENUE_FIELD].notna()] if REVENUE_FIELD in df.columns else pd.DataFrame()
if rev_df.empty:
    st.info("No revenue data in the selected filters.")
    st.stop()

# ── Revenue by destination (supplier country) ─────────────────────────────────
st.subheader("Revenue by Destination")
if "Destination" in rev_df.columns:
    dest = (
        rev_df[rev_df["Destination"] != "Unknown"]
        .groupby("Destination")[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={"Destination": "Country", REVENUE_FIELD: "Revenue"})
        .sort_values("Revenue", ascending=False)
    )
    dest["Label"] = dest["Revenue"].apply(format_currency)

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(
            dest.head(20), x="Country", y="Revenue", text="Label",
            labels={"Country": "", "Revenue": "Revenue (£)"},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_tickangle=-40, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig2 = px.choropleth(
            dest, locations="Country", locationmode="country names",
            color="Revenue", hover_name="Country",
            color_continuous_scale="Blues",
            title="Revenue by Country",
        )
        fig2.update_layout(geo=dict(showframe=False))
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Revenue over time ─────────────────────────────────────────────────────────
st.subheader("Revenue Trend")
if "BookingMonth" in rev_df.columns:
    col_a, col_b = st.columns([1, 3])
    with col_a:
        gran = st.radio("Period", ["Month", "Quarter", "Year"])
    period_col = {"Month": "BookingMonth", "Quarter": "BookingQuarter", "Year": "BookingYear"}[gran]

    trend = (
        rev_df.groupby(period_col)[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={period_col: "Period", REVENUE_FIELD: "Revenue"})
        .sort_values("Period")
    )
    trend["Label"] = trend["Revenue"].apply(format_currency)

    with col_b:
        fig3 = px.line(
            trend, x="Period", y="Revenue", markers=True,
            hover_data={"Label": True, "Revenue": False},
            labels={"Period": "", "Revenue": "Revenue (£)"},
            color_discrete_sequence=[COLOR_SEQUENCE[0]],
        )
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── Top suppliers by revenue ──────────────────────────────────────────────────
st.subheader("Top 20 Suppliers by Revenue")
if "Supplier_Name" in rev_df.columns:
    suppliers = (
        rev_df.dropna(subset=["Supplier_Name"])
        .groupby(["Supplier_Name", "Supplier_Type"])
        .agg(Revenue=(REVENUE_FIELD, "sum"), Bookings=("Id", "count"))
        .reset_index()
        .rename(columns={"Supplier_Name": "Supplier", "Supplier_Type": "Type"})
        .sort_values("Revenue", ascending=False)
        .head(20)
    )
    suppliers["Label"] = suppliers["Revenue"].apply(format_currency)

    fig4 = px.bar(
        suppliers.sort_values("Revenue"), x="Revenue", y="Supplier",
        orientation="h", text="Label", color="Type",
        labels={"Supplier": "", "Revenue": "Revenue (£)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig4.update_traces(textposition="outside")
    fig4.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")

# ── Revenue vs cost breakdown ─────────────────────────────────────────────────
st.subheader("Revenue vs Vendor Cost by Booking Type")
if "Category__c" in rev_df.columns and VENDOR_COST_FIELD in rev_df.columns:
    breakdown = (
        rev_df.groupby("Category__c")
        .agg(Revenue=(REVENUE_FIELD, "sum"), Cost=(VENDOR_COST_FIELD, "sum"))
        .reset_index()
        .rename(columns={"Category__c": "Type"})
        .sort_values("Revenue", ascending=False)
    )
    breakdown["Profit"] = breakdown["Revenue"] - breakdown["Cost"]
    melted = breakdown.melt(id_vars="Type", value_vars=["Revenue", "Cost", "Profit"],
                            var_name="Metric", value_name="Amount (£)")

    fig5 = px.bar(
        melted, x="Type", y="Amount (£)", color="Metric", barmode="group",
        labels={"Type": ""},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig5.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)
