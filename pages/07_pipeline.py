import streamlit as st
import plotly.express as px
import pandas as pd
from data_processor import format_currency
from config import COLOR_SEQUENCE, REVENUE_FIELD, CONFIRMED_STATUSES

st.set_page_config(page_title="Pipeline & Upcoming", page_icon="🗓️", layout="wide")
st.title("🗓️ Pipeline & Upcoming Trips")
st.caption("Confirmed revenue coming in over the next 30, 60, and 90 days.")

df_all = st.session_state.get("df_all", pd.DataFrame())
trip_clients = st.session_state.get("trip_clients", pd.DataFrame())

if df_all.empty:
    st.warning("No data — return to the Home page first.")
    st.stop()

today = pd.Timestamp.now(tz="UTC")

# Future confirmed bookings only
pipeline = df_all[
    (df_all["Booking_Status__c"].isin(CONFIRMED_STATUSES)) &
    (df_all["Date_from__c"].notna()) &
    (df_all["Date_from__c"] > today)
].copy()

pipeline["DaysUntilTrip"] = (pipeline["Date_from__c"] - today).dt.days.astype(int)

# ── KPI buckets ───────────────────────────────────────────────────────────────
next30 = pipeline[pipeline["DaysUntilTrip"] <= 30]
next60 = pipeline[pipeline["DaysUntilTrip"] <= 60]
next90 = pipeline[pipeline["DaysUntilTrip"] <= 90]

def rev(d): return d[REVENUE_FIELD].sum() if REVENUE_FIELD in d.columns else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bookings in next 30 days", f"{len(next30):,}",
          help=f"Revenue: {format_currency(rev(next30))}")
c2.metric("Bookings in next 60 days", f"{len(next60):,}",
          help=f"Revenue: {format_currency(rev(next60))}")
c3.metric("Bookings in next 90 days", f"{len(next90):,}",
          help=f"Revenue: {format_currency(rev(next90))}")
c4.metric("Total pipeline revenue (90d)", format_currency(rev(next90)))

st.markdown("---")

# ── Revenue by month (upcoming) ───────────────────────────────────────────────
st.subheader("Confirmed Revenue by Month (Upcoming)")
if not pipeline.empty and "BookingMonth" in pipeline.columns:
    monthly = (
        pipeline.groupby("BookingMonth")[REVENUE_FIELD]
        .sum().reset_index()
        .rename(columns={"BookingMonth": "Month", REVENUE_FIELD: "Revenue"})
        .sort_values("Month")
    )
    monthly["Label"] = monthly["Revenue"].apply(format_currency)
    fig = px.bar(
        monthly, x="Month", y="Revenue", text="Label",
        labels={"Month": "", "Revenue": "Revenue (£)"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Upcoming trips detail ─────────────────────────────────────────────────────
st.subheader("Upcoming Trips")
window = st.radio("Show trips in the next", ["30 days", "60 days", "90 days", "All upcoming"], horizontal=True)
window_map = {"30 days": 30, "60 days": 60, "90 days": 90, "All upcoming": 99999}
window_days = window_map[window]
view = pipeline[pipeline["DaysUntilTrip"] <= window_days].copy()

if not view.empty:
    # Join client names
    if not trip_clients.empty and "Trip__c" in view.columns:
        lead_clients = trip_clients[trip_clients.get("Lead_Client__c", False) == True][
            ["Trip__c", "Client_Name"]
        ].drop_duplicates("Trip__c") if "Lead_Client__c" in trip_clients.columns else \
            trip_clients[["Trip__c", "Client_Name"]].drop_duplicates("Trip__c")
        view = view.merge(lead_clients, on="Trip__c", how="left")

    display_cols = {
        "Trip_Name": "Trip",
        "Client_Name": "Client",
        "Date_from__c": "Check In",
        "Date_to__c": "Check Out",
        "DaysUntilTrip": "Days Away",
        "Category__c": "Type",
        "Supplier_Name": "Supplier",
        REVENUE_FIELD: "Revenue (£)",
    }
    available = {k: v for k, v in display_cols.items() if k in view.columns}
    disp = view[list(available.keys())].copy()
    disp = disp.rename(columns=available)
    if "Check In" in disp.columns:
        disp["Check In"] = pd.to_datetime(disp["Check In"]).dt.strftime("%d %b %Y")
    if "Check Out" in disp.columns:
        disp["Check Out"] = pd.to_datetime(disp["Check Out"]).dt.strftime("%d %b %Y")
    if "Revenue (£)" in disp.columns:
        disp["Revenue (£)"] = disp["Revenue (£)"].apply(
            lambda x: format_currency(x) if pd.notna(x) else "—"
        )
    disp = disp.sort_values("Days Away")
    st.dataframe(disp, use_container_width=True, hide_index=True)
else:
    st.info(f"No confirmed bookings in the next {window}.")

st.markdown("---")

# ── Trips with accommodation gap ──────────────────────────────────────────────
st.subheader("⚠️ Upcoming Trips with No Hotel Booked")
st.caption("Trips that have confirmed bookings but no accommodation — potential upsell or operational gap.")

if not pipeline.empty and "Trip__c" in pipeline.columns:
    trips_with_hotel = set(
        pipeline[pipeline["Category__c"] == "Accommodation"]["Trip__c"].unique()
    )
    all_upcoming_trips = set(pipeline["Trip__c"].unique())
    no_hotel_trips = all_upcoming_trips - trips_with_hotel

    no_hotel = pipeline[pipeline["Trip__c"].isin(no_hotel_trips)].drop_duplicates("Trip__c")

    if not no_hotel.empty:
        if not trip_clients.empty:
            lead_clients = trip_clients[
                trip_clients.get("Lead_Client__c", False) == True
            ][["Trip__c", "Client_Name"]].drop_duplicates("Trip__c") \
                if "Lead_Client__c" in trip_clients.columns else \
                trip_clients[["Trip__c", "Client_Name"]].drop_duplicates("Trip__c")
            no_hotel = no_hotel.merge(lead_clients, on="Trip__c", how="left")

        nh_cols = {k: v for k, v in {
            "Trip_Name": "Trip", "Client_Name": "Client",
            "Date_from__c": "Date", "DaysUntilTrip": "Days Away"
        }.items() if k in no_hotel.columns}
        nh_disp = no_hotel[list(nh_cols.keys())].rename(columns=nh_cols)
        if "Date" in nh_disp.columns:
            nh_disp["Date"] = pd.to_datetime(nh_disp["Date"]).dt.strftime("%d %b %Y")
        nh_disp = nh_disp.sort_values("Days Away")
        st.dataframe(nh_disp, use_container_width=True, hide_index=True)
        st.caption(f"{len(no_hotel)} upcoming trips have no accommodation booking.")
    else:
        st.success("All upcoming trips have accommodation booked.")

st.markdown("---")

# ── Upcoming by destination ───────────────────────────────────────────────────
st.subheader("Where Are Clients Going? (Next 90 Days)")
if not next90.empty and "Destination" in next90.columns:
    dest = (
        next90[next90["Destination"] != "Unknown"]
        .groupby("Destination").agg(Bookings=("Id", "count"), Revenue=(REVENUE_FIELD, "sum"))
        .reset_index().rename(columns={"Destination": "Country"})
        .sort_values("Bookings", ascending=False)
    )
    fig2 = px.bar(
        dest.head(15), x="Country", y="Bookings",
        labels={"Country": "", "Bookings": "Upcoming Bookings"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig2.update_layout(xaxis_tickangle=-30, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)
