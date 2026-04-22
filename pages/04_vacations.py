import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from data_processor import format_currency
from config import COLOR_SEQUENCE, REVENUE_FIELD
from sidebar import render_filters

st.set_page_config(page_title="Vacation Patterns", page_icon="🏖️", layout="wide")
st.title("🏖️ Vacation Patterns")
st.caption("When people travel, where they go, and how long they stay.")

df, _, _ = render_filters()
if df.empty:
    st.info("No data — check filters or Salesforce credentials.")
    st.stop()

# ── Seasonality heatmap ───────────────────────────────────────────────────────
st.subheader("When Do Trips Happen? (Seasonality)")
if "BookingMonthName" in df.columns and "BookingDayOfWeek" in df.columns:
    month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    heat = (
        df.groupby(["BookingMonthName", "BookingDayOfWeek"]).size()
        .reset_index(name="Bookings")
    )
    heat["BookingMonthName"] = pd.Categorical(heat["BookingMonthName"], categories=month_order, ordered=True)
    heat["BookingDayOfWeek"] = pd.Categorical(heat["BookingDayOfWeek"], categories=day_order, ordered=True)
    heat = heat.sort_values(["BookingMonthName", "BookingDayOfWeek"])
    pivot = heat.pivot(index="BookingDayOfWeek", columns="BookingMonthName", values="Bookings").fillna(0)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale="Blues", hoverongaps=False,
        hovertemplate="Month: %{x}<br>Day: %{y}<br>Bookings: %{z}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Month", yaxis_title="Day of Week", height=350)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Most popular destinations ─────────────────────────────────────────────────
st.subheader("Most Popular Destinations")
if "Destination" in df.columns:
    dest = (
        df[df["Destination"] != "Unknown"]
        .groupby("Destination")
        .agg(Bookings=("Id", "count"), Revenue=(REVENUE_FIELD, "sum"))
        .reset_index()
        .rename(columns={"Destination": "Country"})
        .sort_values("Bookings", ascending=False)
    )

    col_a, col_b = st.columns(2)
    with col_a:
        fig2 = px.bar(
            dest.head(20), x="Bookings", y="Country",
            orientation="h", title="By Number of Bookings",
            labels={"Country": ""},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig2.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        fig3 = px.pie(
            dest.head(12), names="Country", values="Bookings",
            title="Share of Bookings (Top 12)", hole=0.4,
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── Trip duration ─────────────────────────────────────────────────────────────
st.subheader("How Long Are Trips?")
if "NightsDuration" in df.columns and df["NightsDuration"].notna().any():
    dur = df[df["NightsDuration"] > 0]["NightsDuration"]
    avg_dur = dur.mean()
    st.caption(f"Average stay: **{avg_dur:.1f} nights**")

    fig4 = px.histogram(
        dur, nbins=30,
        labels={"value": "Nights", "count": "Bookings"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig4.add_vline(x=avg_dur, line_dash="dash", line_color="red",
                   annotation_text=f"Avg {avg_dur:.0f}n", annotation_position="top right")
    fig4.update_layout(showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("Trip duration requires both check-in and check-out dates on bookings.")

st.markdown("---")

# ── Group size ────────────────────────────────────────────────────────────────
st.subheader("Group Size")
col1, col2 = st.columns(2)

with col1:
    if "TotalTravelers" in df.columns and df["TotalTravelers"].notna().any():
        travelers = df[df["TotalTravelers"] > 0]["TotalTravelers"]
        fig5 = px.histogram(
            travelers, nbins=15,
            labels={"value": "Number of Travelers", "count": "Bookings"},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig5.update_layout(showlegend=False)
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("No traveler count data available.")

with col2:
    if "No_of_Rooms__c" in df.columns and df["No_of_Rooms__c"].notna().any():
        rooms = df[df["No_of_Rooms__c"] > 0]["No_of_Rooms__c"]
        fig6 = px.histogram(
            rooms, nbins=10,
            labels={"value": "Number of Rooms", "count": "Bookings"},
            title="Rooms per Booking",
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig6.update_layout(showlegend=False)
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("No room count data available.")

st.markdown("---")

# ── Trip ratings ──────────────────────────────────────────────────────────────
st.subheader("Client Trip Ratings")
if "Trip_Trip_Rating__c" in df.columns and df["Trip_Trip_Rating__c"].notna().any():
    ratings = (
        df.drop_duplicates("Trip__c")["Trip_Trip_Rating__c"]
        .dropna()
        .value_counts()
        .reset_index()
    )
    ratings.columns = ["Rating", "Count"]
    fig7 = px.bar(
        ratings, x="Rating", y="Count",
        labels={"Rating": "", "Count": "Trips"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig7.update_layout(showlegend=False)
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("No trip ratings recorded yet. Ratings can be added to Trip records in Salesforce.")
