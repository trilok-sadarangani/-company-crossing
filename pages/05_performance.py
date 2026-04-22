import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency
from config import COLOR_SEQUENCE, COLOR_POSITIVE, COLOR_NEGATIVE, REVENUE_FIELD, VENDOR_COST_FIELD

st.set_page_config(page_title="Performance", page_icon="📈", layout="wide")
st.title("📈 Performance")
st.caption("Margins, best and worst destinations, suppliers, and agents.")

df = st.session_state.get("df", pd.DataFrame())
if df.empty:
    st.warning("No data — return to the Home page first.")
    st.stop()

rev_df = df[df[REVENUE_FIELD].notna()] if REVENUE_FIELD in df.columns else pd.DataFrame()

# ── Best vs worst destinations ────────────────────────────────────────────────
st.subheader("Top 5 & Bottom 5 Destinations by Revenue")
if not rev_df.empty and "Destination" in rev_df.columns:
    dest = (
        rev_df[rev_df["Destination"] != "Unknown"]
        .groupby("Destination")[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={"Destination": "Country", REVENUE_FIELD: "Revenue"})
        .sort_values("Revenue", ascending=False)
    )

    if len(dest) >= 4:
        top5 = dest.head(5).copy(); top5["Group"] = "Top 5"
        bot5 = dest.tail(5).copy(); bot5["Group"] = "Bottom 5"
        combined = pd.concat([top5, bot5])
        combined["Label"] = combined["Revenue"].apply(format_currency)

        fig = px.bar(
            combined, x="Country", y="Revenue", color="Group", text="Label",
            labels={"Country": "", "Revenue": "Revenue (£)"},
            color_discrete_map={"Top 5": COLOR_POSITIVE, "Bottom 5": COLOR_NEGATIVE},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Profit by destination ─────────────────────────────────────────────────────
st.subheader("Profit by Destination")
if "Profit_GBP" in rev_df.columns and "Destination" in rev_df.columns:
    profit_dest = (
        rev_df[rev_df["Destination"] != "Unknown"]
        .groupby("Destination")
        .agg(Revenue=(REVENUE_FIELD, "sum"), Profit=("Profit_GBP", "sum"))
        .reset_index()
        .rename(columns={"Destination": "Country"})
        .sort_values("Profit", ascending=False)
    )
    profit_dest["Margin %"] = (profit_dest["Profit"] / profit_dest["Revenue"].replace(0, 1) * 100).round(1)
    profit_dest["Profit Label"] = profit_dest["Profit"].apply(format_currency)

    fig2 = px.bar(
        profit_dest.head(20), x="Country", y="Profit",
        text="Profit Label", color="Margin %",
        color_continuous_scale="RdYlGn", range_color=[0, 30],
        labels={"Country": "", "Profit": "Profit (£)"},
    )
    fig2.update_traces(textposition="outside")
    fig2.update_layout(xaxis_tickangle=-30, coloraxis_showscale=True)
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Supplier performance ──────────────────────────────────────────────────────
st.subheader("Top Suppliers by Revenue")
if "Supplier_Name" in rev_df.columns:
    supp = (
        rev_df.dropna(subset=["Supplier_Name"])
        .groupby(["Supplier_Name", "Supplier_Type"])
        .agg(Revenue=(REVENUE_FIELD, "sum"),
             Bookings=("Id", "count"),
             Profit=("Profit_GBP", "sum") if "Profit_GBP" in rev_df.columns else ("Id", "count"))
        .reset_index()
        .rename(columns={"Supplier_Name": "Supplier", "Supplier_Type": "Type"})
        .sort_values("Revenue", ascending=False)
        .head(25)
    )
    supp["Revenue Label"] = supp["Revenue"].apply(format_currency)

    fig3 = px.bar(
        supp.sort_values("Revenue"), x="Revenue", y="Supplier",
        orientation="h", text="Revenue Label", color="Type",
        labels={"Supplier": "", "Revenue": "Revenue (£)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig3.update_traces(textposition="outside")
    fig3.update_layout(yaxis={"categoryorder": "total ascending"}, height=700)
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── Agent performance ─────────────────────────────────────────────────────────
st.subheader("Agent Performance")
agent_col = "Trip_Owner_Name" if "Trip_Owner_Name" in df.columns else None
if agent_col:
    agent_df = df.drop_duplicates("Trip__c")[["Trip__c", agent_col, "Trip_Status__c"]].copy()
    agent_counts = agent_df.groupby(agent_col).agg(
        Total_Trips=("Trip__c", "count"),
        Completed=(
            "Trip_Status__c",
            lambda x: (x == "✅Completed").sum()
        )
    ).reset_index()

    agent_rev = (
        rev_df.groupby(agent_col)[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={REVENUE_FIELD: "Revenue"})
    ) if agent_col in rev_df.columns else pd.DataFrame()

    if not agent_rev.empty:
        agent_counts = agent_counts.merge(agent_rev, on=agent_col, how="left").fillna(0)
        agent_counts["Revenue Label"] = agent_counts["Revenue"].apply(format_currency)
        agent_counts["Completion Rate %"] = (agent_counts["Completed"] / agent_counts["Total_Trips"] * 100).round(1)
        agent_counts = agent_counts.sort_values("Revenue", ascending=False)
        agent_counts = agent_counts.rename(columns={agent_col: "Agent"})

        col_a, col_b = st.columns(2)
        with col_a:
            fig4 = px.bar(
                agent_counts, x="Agent", y="Revenue",
                text="Revenue Label", title="Revenue by Agent",
                labels={"Agent": "", "Revenue": "Revenue (£)"},
                color_discrete_sequence=COLOR_SEQUENCE,
            )
            fig4.update_traces(textposition="outside")
            fig4.update_layout(xaxis_tickangle=-20, showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)
        with col_b:
            fig5 = px.bar(
                agent_counts, x="Agent", y="Completion Rate %",
                title="Trip Completion Rate by Agent",
                labels={"Agent": ""},
                color="Completion Rate %", color_continuous_scale="RdYlGn", range_color=[0, 100],
            )
            fig5.update_layout(xaxis_tickangle=-20, coloraxis_showscale=False)
            st.plotly_chart(fig5, use_container_width=True)

        with st.expander("Full agent table"):
            display = agent_counts[["Agent", "Total_Trips", "Completed", "Completion Rate %", "Revenue Label"]]
            st.dataframe(display.rename(columns={"Revenue Label": "Revenue"}),
                         use_container_width=True, hide_index=True)
else:
    st.info("Agent data not available — Owner.Name not found on trips.")

st.markdown("---")

# ── Commission analysis ───────────────────────────────────────────────────────
st.subheader("Commission Rate by Supplier Type")
if "Commission_from_Vendor__c" in df.columns and "Category__c" in df.columns:
    comm = (
        df[df["Commission_from_Vendor__c"].notna()]
        .groupby("Category__c")["Commission_from_Vendor__c"]
        .mean().reset_index()
        .rename(columns={"Category__c": "Type", "Commission_from_Vendor__c": "Avg Commission %"})
        .sort_values("Avg Commission %", ascending=False)
    )
    fig6 = px.bar(
        comm, x="Type", y="Avg Commission %",
        labels={"Type": "", "Avg Commission %": "Avg Commission (%)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig6.update_layout(xaxis_tickangle=-30, showlegend=False)
    st.plotly_chart(fig6, use_container_width=True)

st.markdown("---")

# ── Margin by booking category ────────────────────────────────────────────────
st.subheader("Margin % by Booking Type")
st.caption("Which types of bookings are most profitable per £ billed.")
if "Profit_GBP" in rev_df.columns and "Category__c" in rev_df.columns:
    margin_cat = (
        rev_df.groupby("Category__c")
        .agg(Revenue=(REVENUE_FIELD, "sum"), Profit=("Profit_GBP", "sum"), Bookings=("Id", "count"))
        .reset_index()
        .rename(columns={"Category__c": "Type"})
    )
    margin_cat["Margin %"] = (margin_cat["Profit"] / margin_cat["Revenue"].replace(0, 1) * 100).round(1)
    margin_cat = margin_cat.sort_values("Margin %", ascending=False)

    fig7 = px.bar(
        margin_cat, x="Type", y="Margin %",
        color="Margin %", color_continuous_scale="RdYlGn", range_color=[0, 30],
        labels={"Type": ""},
        text=margin_cat["Margin %"].apply(lambda x: f"{x:.1f}%"),
    )
    fig7.update_traces(textposition="outside")
    fig7.update_layout(xaxis_tickangle=-30, coloraxis_showscale=False, showlegend=False)
    st.plotly_chart(fig7, use_container_width=True)

st.markdown("---")

# ── Margin by client origin ───────────────────────────────────────────────────
st.subheader("Margin % by Client Home Country")
st.caption("Do clients from certain countries generate better margins?")
if "Profit_GBP" in rev_df.columns and "Trip_Client_Location__c" in rev_df.columns:
    origin = rev_df[rev_df["Trip_Client_Location__c"].notna()]
    if not origin.empty:
        margin_origin = (
            origin.groupby("Trip_Client_Location__c")
            .agg(Revenue=(REVENUE_FIELD, "sum"), Profit=("Profit_GBP", "sum"), Trips=("Trip__c", "nunique"))
            .reset_index()
            .rename(columns={"Trip_Client_Location__c": "Country"})
        )
        margin_origin["Margin %"] = (margin_origin["Profit"] / margin_origin["Revenue"].replace(0, 1) * 100).round(1)
        margin_origin = margin_origin[margin_origin["Revenue"] > 0].sort_values("Margin %", ascending=False)

        col_a, col_b = st.columns(2)
        with col_a:
            fig8 = px.bar(
                margin_origin, x="Country", y="Margin %",
                color="Margin %", color_continuous_scale="RdYlGn", range_color=[0, 30],
                text=margin_origin["Margin %"].apply(lambda x: f"{x:.1f}%"),
                labels={"Country": ""},
            )
            fig8.update_traces(textposition="outside")
            fig8.update_layout(coloraxis_showscale=False, showlegend=False, xaxis_tickangle=-20)
            st.plotly_chart(fig8, use_container_width=True)
        with col_b:
            fig9 = px.scatter(
                margin_origin, x="Revenue", y="Margin %",
                size="Trips", hover_name="Country", color="Country",
                labels={"Revenue": "Total Revenue (£)", "Margin %": "Margin %"},
                color_discrete_sequence=COLOR_SEQUENCE,
            )
            fig9.update_layout(showlegend=False)
            st.plotly_chart(fig9, use_container_width=True)

st.markdown("---")

# ── Sweet spot: volume vs margin by destination ───────────────────────────────
st.subheader("🎯 Sweet Spot — Volume vs Margin by Destination")
st.caption("Bigger bubbles = more revenue. Top-right = high bookings AND high margin — your ideal focus destinations.")
if "Profit_GBP" in rev_df.columns and "Destination" in rev_df.columns:
    sweet = (
        rev_df[rev_df["Destination"] != "Unknown"]
        .groupby("Destination")
        .agg(
            Revenue=(REVENUE_FIELD, "sum"),
            Profit=("Profit_GBP", "sum"),
            Bookings=("Id", "count"),
        )
        .reset_index()
        .rename(columns={"Destination": "Country"})
    )
    sweet["Margin %"] = (sweet["Profit"] / sweet["Revenue"].replace(0, 1) * 100).round(1)
    sweet = sweet[sweet["Revenue"] > 0]

    fig10 = px.scatter(
        sweet, x="Bookings", y="Margin %",
        size="Revenue", hover_name="Country", color="Country",
        text="Country",
        labels={"Bookings": "Number of Bookings", "Margin %": "Profit Margin %"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig10.update_traces(textposition="top center")
    fig10.update_layout(showlegend=False, height=520)
    # Add quadrant lines at medians
    if not sweet.empty:
        med_x = sweet["Bookings"].median()
        med_y = sweet["Margin %"].median()
        fig10.add_vline(x=med_x, line_dash="dot", line_color="gray", opacity=0.5)
        fig10.add_hline(y=med_y, line_dash="dot", line_color="gray", opacity=0.5)
    st.plotly_chart(fig10, use_container_width=True)
    st.caption("Dashed lines = median. Top-right quadrant = high volume, high margin — prioritise these.")
