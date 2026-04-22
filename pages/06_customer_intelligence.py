import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import build_client_metrics, format_currency
from config import COLOR_SEQUENCE
from sidebar import render_filters

st.set_page_config(page_title="Customer Intelligence", page_icon="🎯", layout="wide")
st.title("🎯 Customer Intelligence")
st.caption("Re-engagement targets, loyalty segments, and booking patterns — so you know exactly who to call.")

_, df, trip_clients = render_filters()

if df.empty or trip_clients.empty:
    st.info("No data — check Salesforce credentials.")
    st.stop()

metrics = build_client_metrics(trip_clients, df)
if metrics.empty:
    st.info("Not enough data to build client metrics yet.")
    st.stop()

today = pd.Timestamp.now(tz="UTC")

# ── Segment summary ───────────────────────────────────────────────────────────
st.subheader("Client Segments at a Glance")
seg_counts = metrics["Segment"].value_counts().reset_index()
seg_counts.columns = ["Segment", "Clients"]

col_a, col_b = st.columns(2)
with col_a:
    fig = px.bar(
        seg_counts, x="Clients", y="Segment", orientation="h",
        labels={"Segment": "", "Clients": "Number of Clients"},
        color="Segment", color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)
with col_b:
    seg_spend = metrics.groupby("Segment")["TotalSpend"].sum().reset_index()
    seg_spend["Label"] = seg_spend["TotalSpend"].apply(format_currency)
    fig2 = px.pie(
        seg_spend, names="Segment", values="TotalSpend",
        hole=0.4, color_discrete_sequence=COLOR_SEQUENCE,
        title="Revenue Share by Segment",
    )
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("""
| Segment | What it means |
|---|---|
| ⭐ Champion | Books often, spends big, came recently — your VIPs |
| 💚 Loyal | Consistent bookers, strong relationship |
| 🌱 Promising | Booked recently but not often yet — nurture them |
| ⚠️ At Risk | Used to book frequently but gone quiet recently |
| 🚨 Can't Lose | High spenders who haven't been back in a while — call them now |
| 1️⃣ One-Time | Booked once and never returned |
| 💤 Lapsed | Haven't booked in a very long time |
| ➡️ Regular | Steady mid-tier clients |
""")

st.markdown("---")

# ── Re-engagement targets ─────────────────────────────────────────────────────
st.subheader("🚨 Priority Re-engagement Targets")
st.caption("High-value clients who haven't booked recently — most likely to generate revenue if contacted.")

lapse_months = st.slider("Show clients who haven't booked in more than X months", 6, 24, 12)
lapse_days = lapse_months * 30

at_risk = metrics[
    (metrics["DaysSinceLastTrip"] >= lapse_days) &
    (metrics["TotalSpend"] > 0)
].sort_values("TotalSpend", ascending=False)

if not at_risk.empty:
    display = at_risk[["Client", "Segment", "TotalSpend", "TripCount",
                        "DaysSinceLastTrip", "LastTripDate"]].copy()
    display["TotalSpend"] = display["TotalSpend"].apply(format_currency)
    display["LastTripDate"] = display["LastTripDate"].dt.strftime("%b %Y")
    display["DaysSinceLastTrip"] = display["DaysSinceLastTrip"].astype(int).astype(str) + " days"
    display = display.rename(columns={
        "TotalSpend": "Lifetime Spend",
        "TripCount": "Trips",
        "DaysSinceLastTrip": "Last Booked",
        "LastTripDate": "Last Trip",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(f"{len(at_risk)} clients haven't booked in {lapse_months}+ months · "
               f"Combined lifetime spend: {format_currency(at_risk['TotalSpend'].sum())}")
else:
    st.info("No lapsed clients found for the selected threshold.")

st.markdown("---")

# ── Can't Lose + At Risk highlight ────────────────────────────────────────────
st.subheader("⚠️ At Risk & Can't Lose — Call List")
priority = metrics[metrics["Segment"].isin(["🚨 Can't Lose", "⚠️ At Risk"])].sort_values("TotalSpend", ascending=False)

if not priority.empty:
    fig3 = px.scatter(
        priority,
        x="DaysSinceLastTrip", y="TotalSpend",
        size="TripCount", color="Segment", hover_name="Client",
        labels={"DaysSinceLastTrip": "Days Since Last Trip", "TotalSpend": "Lifetime Spend (£)"},
        color_discrete_sequence=["#d62728", "#ff7f0e"],
    )
    fig3.update_layout(showlegend=True)
    st.plotly_chart(fig3, use_container_width=True)

    display2 = priority[["Client", "Segment", "TotalSpend", "TripCount", "DaysSinceLastTrip", "LastTripDate"]].copy()
    display2["TotalSpend"] = display2["TotalSpend"].apply(format_currency)
    display2["LastTripDate"] = display2["LastTripDate"].dt.strftime("%b %Y")
    display2["DaysSinceLastTrip"] = display2["DaysSinceLastTrip"].astype(int).astype(str) + " days"
    st.dataframe(display2.rename(columns={
        "TotalSpend": "Lifetime Spend", "TripCount": "Trips",
        "DaysSinceLastTrip": "Last Booked", "LastTripDate": "Last Trip",
    }), use_container_width=True, hide_index=True)

st.markdown("---")

# ── One-and-done clients ──────────────────────────────────────────────────────
st.subheader("1️⃣ One-Time Clients — Win-Back Opportunities")
one_time = metrics[metrics["TripCount"] == 1].sort_values("TotalSpend", ascending=False)
st.caption(f"{len(one_time)} clients booked exactly once and never returned.")

if not one_time.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("One-time clients", f"{len(one_time):,}")
    col2.metric("Combined spend", format_currency(one_time["TotalSpend"].sum()))
    col3.metric("Avg spend per client", format_currency(one_time["TotalSpend"].mean()))

    display3 = one_time[["Client", "TotalSpend", "LastTripDate", "DaysSinceLastTrip"]].copy()
    display3["TotalSpend"] = display3["TotalSpend"].apply(format_currency)
    display3["LastTripDate"] = display3["LastTripDate"].dt.strftime("%b %Y")
    display3["DaysSinceLastTrip"] = display3["DaysSinceLastTrip"].astype(int).astype(str) + " days"
    st.dataframe(display3.rename(columns={
        "TotalSpend": "Spend", "LastTripDate": "Trip Date", "DaysSinceLastTrip": "Days Ago"
    }).head(30), use_container_width=True, hide_index=True)

st.markdown("---")

# ── Booking cadence ───────────────────────────────────────────────────────────
st.subheader("📅 Booking Cadence — Who Travels on a Schedule?")
cadence = metrics[metrics["AvgDaysBetweenTrips"].notna()].sort_values("AvgDaysBetweenTrips")

if not cadence.empty:
    cadence["AvgMonthsBetween"] = (cadence["AvgDaysBetweenTrips"] / 30).round(1)
    fig4 = px.histogram(
        cadence, x="AvgMonthsBetween", nbins=20,
        labels={"AvgMonthsBetween": "Avg Months Between Trips", "count": "Clients"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig4.update_layout(showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

    st.caption("Clients who book every 3-6 months are your most predictable revenue — reach out proactively before their next window.")
    frequent = cadence[cadence["AvgDaysBetweenTrips"] <= 120].sort_values("TotalSpend", ascending=False)
    if not frequent.empty:
        st.markdown("**Clients who book every 4 months or less:**")
        display4 = frequent[["Client", "TripCount", "AvgMonthsBetween", "TotalSpend"]].copy()
        display4["TotalSpend"] = display4["TotalSpend"].apply(format_currency)
        st.dataframe(display4.rename(columns={
            "TripCount": "Trips", "AvgMonthsBetween": "Avg Months Between Trips",
            "TotalSpend": "Lifetime Spend"
        }), use_container_width=True, hide_index=True)

st.markdown("---")

# ── Full RFM table ────────────────────────────────────────────────────────────
st.subheader("📊 Full Client Scorecard")
with st.expander("View all clients with RFM scores"):
    full = metrics[["Client", "Segment", "TotalSpend", "TripCount",
                     "DaysSinceLastTrip", "LastTripDate", "R", "F", "M", "RFM_Score"]].copy()
    full["TotalSpend"] = full["TotalSpend"].apply(format_currency)
    full["LastTripDate"] = full["LastTripDate"].dt.strftime("%b %Y")
    full["DaysSinceLastTrip"] = full["DaysSinceLastTrip"].astype(int)
    st.dataframe(full.rename(columns={
        "TotalSpend": "Lifetime Spend", "TripCount": "Trips",
        "DaysSinceLastTrip": "Days Since Last Trip", "LastTripDate": "Last Trip",
    }), use_container_width=True, hide_index=True)
