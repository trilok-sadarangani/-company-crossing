import pandas as pd
import streamlit as st
from salesforce_client import load_bookings, load_trip_clients
from data_processor import enrich, apply_filters
from config import CONFIRMED_STATUSES


def render_filters():
    """Load data, render sidebar filters, return (filtered_df, df_all, trip_clients)."""
    bookings_raw = load_bookings()
    trip_clients = load_trip_clients()

    if bookings_raw.empty:
        st.sidebar.warning("No Salesforce data loaded.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = enrich(bookings_raw)

    st.sidebar.header("Filters")
    st.sidebar.caption("Apply to all pages.")

    valid_dates = df["Date_from__c"].dropna()
    min_date = valid_dates.min().date() if not valid_dates.empty else pd.Timestamp("2020-01-01").date()
    max_date = valid_dates.max().date() if not valid_dates.empty else pd.Timestamp.today().date()

    start_date = st.sidebar.date_input(
        "From", value=min_date, min_value=min_date, max_value=max_date, key="filter_start"
    )
    end_date = st.sidebar.date_input(
        "To", value=max_date, min_value=min_date, max_value=max_date, key="filter_end"
    )

    all_categories = sorted(df["Category__c"].dropna().unique().tolist()) if "Category__c" in df.columns else []
    selected_categories = st.sidebar.multiselect(
        "Booking Type", options=all_categories, default=all_categories,
        help="Filter by type of service booked", key="filter_categories"
    )

    all_statuses = sorted(df["Booking_Status__c"].dropna().unique().tolist()) if "Booking_Status__c" in df.columns else []
    selected_statuses = st.sidebar.multiselect(
        "Booking Status", options=all_statuses, default=CONFIRMED_STATUSES,
        help="Confirmed = active/completed bookings. Add cancelled here if needed.", key="filter_statuses"
    )

    if "Date_from__c" in df.columns:
        undated = df["Date_from__c"].isna().sum()
        if undated > 0:
            st.sidebar.info(f"{undated:,} bookings have no date and are excluded from time-based charts.")

    filtered_df = apply_filters(df, start_date, end_date, selected_categories, selected_statuses)
    return filtered_df, df, trip_clients
