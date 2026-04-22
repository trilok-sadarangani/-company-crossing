import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency, top_clients
from config import COLOR_SEQUENCE, COLOR_POSITIVE, COLOR_NEUTRAL, REVENUE_FIELD
from sidebar import render_filters

st.set_page_config(page_title="Customer Insights", page_icon="👥", layout="wide")
st.title("👥 Customer Insights")
st.caption("Who your customers are, where they come from, and how much they spend.")

df, _, trip_clients = render_filters()
if df.empty:
    st.info("No data — check filters or Salesforce credentials.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_clients = trip_clients["Client__c"].nunique() if not trip_clients.empty else 0
total_trips = trip_clients["Trip__c"].nunique() if not trip_clients.empty else 0
# Clients with more than one trip = repeat
if not trip_clients.empty:
    trips_per_client = trip_clients.groupby("Client__c")["Trip__c"].nunique()
    repeat_clients = (trips_per_client > 1).sum()
    avg_trips = trips_per_client.mean()
else:
    repeat_clients = 0
    avg_trips = 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Clients", f"{total_clients:,}")
c2.metric("Repeat Clients", f"{repeat_clients:,}", help="Clients with more than 1 trip")
c3.metric("Total Trips", f"{total_trips:,}")
c4.metric("Avg Trips per Client", f"{avg_trips:.1f}")

st.markdown("---")

# ── Top clients by revenue ────────────────────────────────────────────────────
st.subheader("Top 20 Clients by Revenue")
top = top_clients(trip_clients, df, n=20)
if not top.empty:
    top["Label"] = top["Revenue_GBP"].apply(format_currency)
    fig = px.bar(
        top.sort_values("Revenue_GBP"), x="Revenue_GBP", y="Client",
        orientation="h", text="Label",
        labels={"Client": "", "Revenue_GBP": "Revenue (£)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Full table"):
        st.dataframe(top.rename(columns={"Revenue_GBP": "Revenue (£)", "Label": "Formatted"})[["Client", "Revenue (£)", "Formatted"]],
                     use_container_width=True, hide_index=True)

st.markdown("---")

# ── Client trips frequency ────────────────────────────────────────────────────
st.subheader("How Often Do Clients Travel?")
if not trip_clients.empty:
    freq = trips_per_client.value_counts().reset_index()
    freq.columns = ["Number of Trips", "Clients"]
    freq = freq.sort_values("Number of Trips")

    fig2 = px.bar(
        freq, x="Number of Trips", y="Clients",
        labels={"Number of Trips": "Trips Booked", "Clients": "Number of Clients"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Where clients come from ───────────────────────────────────────────────────
st.subheader("Where Your Clients Come From")
if "Trip_Client_Location__c" in df.columns and df["Trip_Client_Location__c"].notna().any():
    locations = (
        df[df["Trip_Client_Location__c"].notna()]
        .drop_duplicates(subset="Trip__c")[["Trip__c", "Trip_Client_Location__c"]]
        .groupby("Trip_Client_Location__c").size()
        .reset_index(name="Trips")
        .sort_values("Trips", ascending=False)
        .rename(columns={"Trip_Client_Location__c": "Location"})
    )

    col_a, col_b = st.columns(2)
    with col_a:
        fig3 = px.bar(
            locations.head(15), x="Location", y="Trips",
            labels={"Location": "", "Trips": "Trips"},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig3.update_layout(xaxis_tickangle=-30, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)
    with col_b:
        fig4 = px.choropleth(
            locations, locations="Location", locationmode="country names",
            color="Trips", hover_name="Location",
            color_continuous_scale="Blues",
        )
        fig4.update_layout(geo=dict(showframe=False))
        st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("Client location data is partially populated in Salesforce. As more trips are added with Client Location, this map will fill in.")

st.markdown("---")

# ── New clients over time ─────────────────────────────────────────────────────
st.subheader("New Clients Over Time")
if not trip_clients.empty and "Trip__c" in trip_clients.columns:
    # Join trip start date to trip_clients — only past months
    today = pd.Timestamp.now(tz="UTC").normalize()
    trip_dates = (
        df[["Trip__c", "BookingMonth"]].drop_duplicates("Trip__c").dropna()
    )
    trip_dates = trip_dates[trip_dates["BookingMonth"] <= today]
    first_trip = (
        trip_clients.merge(trip_dates, on="Trip__c", how="inner")
        .groupby("Client__c")["BookingMonth"].min()
        .reset_index()
        .rename(columns={"BookingMonth": "FirstTripMonth"})
    )
    new_by_month = (
        first_trip.groupby("FirstTripMonth").size()
        .reset_index(name="New Clients")
        .sort_values("FirstTripMonth")
    )

    fig5 = px.bar(
        new_by_month, x="FirstTripMonth", y="New Clients",
        labels={"FirstTripMonth": "", "New Clients": "New Clients"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig5.update_layout(showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)
