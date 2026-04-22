import os
import pandas as pd
import streamlit as st
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Read from Streamlit secrets (cloud) or environment variables (local)."""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)


@st.cache_resource(show_spinner="Connecting to Salesforce…")
def get_salesforce() -> Salesforce | None:
    username = _get_secret("SF_USERNAME")
    password = _get_secret("SF_PASSWORD")
    token = _get_secret("SF_TOKEN")
    domain = _get_secret("SF_DOMAIN") or "login"

    if not all([username, password, token]):
        return None
    try:
        return Salesforce(username=username, password=password,
                          security_token=token, domain=domain)
    except SalesforceAuthenticationFailed as e:
        st.error(f"Salesforce login failed: {e}")
        return None


def _records_to_df(records: list) -> pd.DataFrame:
    rows = []
    for r in records:
        row = {k: v for k, v in r.items() if k != "attributes"}
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _flatten_lookup(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
    """Flatten a Salesforce relationship dict column into prefixed columns."""
    if col not in df.columns:
        return df
    expanded = df[col].apply(
        lambda x: {f"{prefix}_{k}": v for k, v in x.items() if k != "attributes"}
        if isinstance(x, dict) else {}
    )
    expanded_df = pd.DataFrame(expanded.tolist(), index=df.index)
    df = pd.concat([df.drop(columns=[col]), expanded_df], axis=1)
    return df


@st.cache_data(ttl=300, show_spinner="Loading bookings…")
def load_bookings() -> pd.DataFrame:
    sf = get_salesforce()
    if sf is None:
        return pd.DataFrame()
    try:
        query = """
            SELECT Id, Name, Category__c, Vendor__c, Booking_Status__c,
                   Billed_Amount_GBP__c, Vendor_Payment_Amount_GBP__c,
                   Billed_Amount__c, Billed_Currency__c,
                   Commission_from_Vendor__c, Commission_Amount__c,
                   No_of_Rooms__c, No_of_Adults__c, No_of_Children__c,
                   Date_from__c, Date_to__c,
                   Trip__c,
                   Trip__r.Name, Trip__r.Status__c,
                   Trip__r.Trip_Start_Date__c, Trip__r.Trip_End_Date__c,
                   Trip__r.Client_Location__c, Trip__r.Trip_Rating__c,
                   Trip__r.OwnerId, Trip__r.Owner.Name,
                   Supplier__c,
                   Supplier__r.Name, Supplier__r.Type,
                   Supplier__r.BillingCity, Supplier__r.BillingCountry
            FROM Booking__c
        """
        records = sf.query_all(query)["records"]
        df = _records_to_df(records)
        df = _flatten_lookup(df, "Trip__r", "Trip")
        df = _flatten_lookup(df, "Supplier__r", "Supplier")
        # parse dates
        for col in ["Date_from__c", "Date_to__c",
                    "Trip_Trip_Start_Date__c", "Trip_Trip_End_Date__c"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
        return df
    except Exception as e:
        st.error(f"Could not load Bookings: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner="Loading clients…")
def load_trip_clients() -> pd.DataFrame:
    """Returns one row per (trip, client) with client account name."""
    sf = get_salesforce()
    if sf is None:
        return pd.DataFrame()
    try:
        query = """
            SELECT Trip__c, Trip__r.Name, Lead_Client__c,
                   Client__c, Client__r.Name, Client__r.BillingCountry
            FROM Trip_Client__c
        """
        records = sf.query_all(query)["records"]
        df = _records_to_df(records)
        df = _flatten_lookup(df, "Trip__r", "Trip")
        df = _flatten_lookup(df, "Client__r", "Client")
        return df
    except Exception as e:
        st.error(f"Could not load Trip Clients: {e}")
        return pd.DataFrame()
