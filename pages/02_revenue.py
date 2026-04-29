import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency
from config import COLOR_SEQUENCE, REVENUE_FIELD, VENDOR_COST_FIELD
from sidebar import render_filters

st.set_page_config(page_title="Revenue Analysis", page_icon="💰", layout="wide")
st.title("💰 Revenue Analysis")
st.caption("Where your money comes from — by destination, supplier, and period.")

df, _, _ = render_filters()
if df.empty:
    st.info("No data — check filters or Salesforce credentials.")
    st.stop()

rev_df = df[df[REVENUE_FIELD].notna()] if REVENUE_FIELD in df.columns else pd.DataFrame()
if rev_df.empty:
    st.info("No revenue data in the selected filters.")
    st.stop()

# ── Revenue by destination (supplier country) ─────────────────────────────────
st.subheader("Revenue by Destination")
st.caption("The bar ranks your top earners; the map shows geographic concentration. Heavy reliance on one or two countries is a risk — if travel to that region is disrupted, revenue takes a direct hit. Diversification across destinations improves resilience.")
if "Destination" in rev_df.columns:
    dest = (
        rev_df[rev_df["Destination"] != "Unknown"]
        .groupby("Destination")[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={"Destination": "Country", REVENUE_FIELD: "Revenue"})
        .sort_values("Revenue", ascending=False)
    )
    dest["Label"] = dest["Revenue"].apply(format_currency)

    top5 = dest.head(5)
    bottom5 = dest.tail(5).sort_values("Revenue")
    combined = pd.concat([
        top5.assign(Group="Top 5"),
        bottom5.assign(Group="Bottom 5"),
    ])

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(
            combined, x="Country", y="Revenue", text="Label", color="Group",
            labels={"Country": "", "Revenue": "Revenue (£)"},
            color_discrete_map={"Top 5": "#1a6fa8", "Bottom 5": "#e05a3a"},
            category_orders={"Country": list(top5["Country"]) + list(bottom5["Country"])},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_tickangle=-40, showlegend=True, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

        # Search any destination not in Top/Bottom 5
        all_countries = dest["Country"].tolist()
        search_dest = st.selectbox(
            "Look up any destination",
            options=[""] + all_countries,
            format_func=lambda x: "— search all destinations —" if x == "" else x,
            key="dest_search",
        )
        if search_dest:
            row = dest[dest["Country"] == search_dest].iloc[0]
            rank = dest["Country"].tolist().index(search_dest) + 1
            st.metric(
                label=f"{search_dest} (Rank #{rank} of {len(dest)})",
                value=row["Label"],
            )

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
st.caption("Use Month for granular patterns, Quarter to smooth out noise, Year for strategic growth view. A consistent upward slope is the goal — look for the periods where revenue dipped and cross-reference with what was happening commercially at that time.")
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
st.caption("Suppliers near the top are key relationships — treat them as partners, not just vendors. If one supplier dominates, you have pricing leverage but also dependency risk. Colour shows supplier type, so you can see which categories your top partners fall into.")
if "Supplier_Name" in rev_df.columns:
    all_suppliers = (
        rev_df.dropna(subset=["Supplier_Name"])
        .groupby(["Supplier_Name", "Supplier_Type"])
        .agg(Revenue=(REVENUE_FIELD, "sum"), Bookings=("Id", "count"))
        .reset_index()
        .rename(columns={"Supplier_Name": "Supplier", "Supplier_Type": "Type"})
        .sort_values("Revenue", ascending=False)
    )
    all_suppliers["Label"] = all_suppliers["Revenue"].apply(format_currency)
    suppliers = all_suppliers.head(20)

    fig4 = px.bar(
        suppliers.sort_values("Revenue"), x="Revenue", y="Supplier",
        orientation="h", text="Label", color="Type",
        labels={"Supplier": "", "Revenue": "Revenue (£)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig4.update_traces(textposition="outside")
    fig4.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig4, use_container_width=True)

    search_sup = st.selectbox(
        "Look up any supplier",
        options=[""] + all_suppliers["Supplier"].tolist(),
        format_func=lambda x: "— search all suppliers —" if x == "" else x,
        key="supplier_search",
    )
    if search_sup:
        row = all_suppliers[all_suppliers["Supplier"] == search_sup].iloc[0]
        rank = all_suppliers["Supplier"].tolist().index(search_sup) + 1
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Rank #{rank} of {len(all_suppliers)}", row["Label"], help="Total revenue")
        c2.metric("Bookings", int(row["Bookings"]))
        c3.metric("Type", row["Type"] if pd.notna(row["Type"]) else "—")

st.markdown("---")

# ── Revenue vs cost breakdown ─────────────────────────────────────────────────
st.subheader("Revenue vs Vendor Cost by Booking Type")
st.caption("The gap between the Revenue and Cost bars is your gross profit per booking type. A small gap means thin margins — ask whether your pricing reflects the effort and risk involved. The Profit bar makes the gap explicit.")
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
