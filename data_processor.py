import pandas as pd
from config import CONFIRMED_STATUSES, ACTIVE_TRIP_STATUSES, REVENUE_FIELD, VENDOR_COST_FIELD
from data_cleanup import load_mappings, apply_mapping


def confirmed(df: pd.DataFrame) -> pd.DataFrame:
    if "Booking_Status__c" not in df.columns:
        return df
    return df[df["Booking_Status__c"].isin(CONFIRMED_STATUSES)]


def active_trips(df: pd.DataFrame) -> pd.DataFrame:
    col = "Trip_Status__c"
    if col not in df.columns:
        return df
    return df[df[col].isin(ACTIVE_TRIP_STATUSES)]


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    date_col = "Date_from__c"
    if date_col in df.columns:
        df["BookingMonth"] = df[date_col].dt.to_period("M").dt.to_timestamp()
        df["BookingQuarter"] = df[date_col].dt.to_period("Q").dt.to_timestamp()
        df["BookingYear"] = df[date_col].dt.year
        df["BookingMonthName"] = df[date_col].dt.strftime("%b")
        df["BookingDayOfWeek"] = df[date_col].dt.day_name()

    # Duration in nights
    if "Date_from__c" in df.columns and "Date_to__c" in df.columns:
        df["NightsDuration"] = (df["Date_to__c"] - df["Date_from__c"]).dt.days.clip(lower=0)

    # Total travelers
    if "No_of_Adults__c" in df.columns:
        adults = df["No_of_Adults__c"].fillna(0)
        children = df["No_of_Children__c"].fillna(0) if "No_of_Children__c" in df.columns else 0
        df["TotalTravelers"] = adults + children

    # Profit per booking
    if REVENUE_FIELD in df.columns and VENDOR_COST_FIELD in df.columns:
        df["Profit_GBP"] = df[REVENUE_FIELD].fillna(0) - df[VENDOR_COST_FIELD].fillna(0)

    # Fix category typo and null categories
    if "Category__c" in df.columns:
        df["Category__c"] = df["Category__c"].replace("Accomodation", "Accommodation").fillna("Uncategorized")

    # Destination = supplier country, fall back to trip client location
    dest = "Unknown"
    if "Supplier_BillingCountry" in df.columns:
        df["Destination"] = df["Supplier_BillingCountry"].fillna(
            df.get("Trip_Client_Location__c", dest)
        ).fillna(dest)
    elif "Trip_Client_Location__c" in df.columns:
        df["Destination"] = df["Trip_Client_Location__c"].fillna(dest)
    else:
        df["Destination"] = dest

    # Apply canonical name mappings (defined via the Data Cleanup page)
    mappings = load_mappings()
    if "Supplier_Name" in df.columns:
        df["Supplier_Name"] = apply_mapping(df["Supplier_Name"], mappings["suppliers"])
    if "Destination" in df.columns:
        df["Destination"] = apply_mapping(df["Destination"], mappings["destinations"])

    return df


def apply_filters(df: pd.DataFrame, start_date, end_date, categories: list[str],
                  statuses: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    if "Date_from__c" in df.columns:
        df = df[
            (df["Date_from__c"] >= pd.Timestamp(start_date, tz="UTC")) &
            (df["Date_from__c"] <= pd.Timestamp(end_date, tz="UTC"))
        ]

    if categories and "Category__c" in df.columns:
        df = df[df["Category__c"].isin(categories)]

    if statuses and "Booking_Status__c" in df.columns:
        df = df[df["Booking_Status__c"].isin(statuses)]

    return df


def format_currency(value: float, symbol: str = "£") -> str:
    if pd.isna(value) or value == 0:
        return f"{symbol}0"
    if abs(value) >= 1_000_000:
        return f"{symbol}{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{symbol}{value / 1_000:.1f}K"
    return f"{symbol}{value:,.0f}"


TEST_KEYWORDS = ["test", "sample", "dummy", "demo"]


def _clean_clients(trip_clients: pd.DataFrame) -> pd.DataFrame:
    """Remove test/sample accounts and apply canonical name mappings."""
    if "Client_Name" not in trip_clients.columns:
        return trip_clients
    mask = trip_clients["Client_Name"].str.lower().str.contains(
        "|".join(TEST_KEYWORDS), na=False
    )
    cleaned = trip_clients[~mask].copy()
    client_mapping = load_mappings().get("clients", {})
    if client_mapping:
        cleaned["Client_Name"] = apply_mapping(cleaned["Client_Name"], client_mapping)
    return cleaned


def build_client_metrics(trip_clients: pd.DataFrame, bookings: pd.DataFrame) -> pd.DataFrame:
    """
    One row per client with recency, frequency, monetary, and RFM segment.
    Used by the Customer Intelligence page.
    """
    if trip_clients.empty or bookings.empty:
        return pd.DataFrame()

    tc = _clean_clients(trip_clients.copy())
    today = pd.Timestamp.now(tz="UTC")

    # Past confirmed bookings with dates
    past = bookings[
        bookings["Booking_Status__c"].isin(CONFIRMED_STATUSES) &
        bookings["Date_from__c"].notna() &
        (bookings["Date_from__c"] <= today)
    ][["Trip__c", "Date_from__c", REVENUE_FIELD]].copy()

    # Join clients → trips → bookings
    merged = tc.merge(past, on="Trip__c", how="inner")
    if merged.empty:
        return pd.DataFrame()

    client_col = "Client_Name" if "Client_Name" in merged.columns else "Client__c"

    agg = merged.groupby(client_col).agg(
        LastTripDate=("Date_from__c", "max"),
        FirstTripDate=("Date_from__c", "min"),
        TripCount=("Trip__c", "nunique"),
        TotalSpend=(REVENUE_FIELD, "sum"),
    ).reset_index().rename(columns={client_col: "Client"})

    agg["DaysSinceLastTrip"] = (today - agg["LastTripDate"]).dt.days
    agg["TotalSpend"] = agg["TotalSpend"].fillna(0)

    # Average days between trips (only meaningful for 2+ trips)
    span = (agg["LastTripDate"] - agg["FirstTripDate"]).dt.days
    agg["AvgDaysBetweenTrips"] = (span / (agg["TripCount"] - 1)).where(agg["TripCount"] > 1)

    # RFM quintile scores (1=worst, 5=best)
    def quintile(series, ascending=True):
        try:
            return pd.qcut(series.rank(method="first"), 5,
                           labels=[1, 2, 3, 4, 5] if ascending else [5, 4, 3, 2, 1])
        except Exception:
            return pd.Series(3, index=series.index)

    agg["R"] = quintile(agg["DaysSinceLastTrip"], ascending=False).astype(int)  # lower days = higher score
    agg["F"] = quintile(agg["TripCount"], ascending=True).astype(int)
    agg["M"] = quintile(agg["TotalSpend"], ascending=True).astype(int)
    agg["RFM_Score"] = agg["R"] * 100 + agg["F"] * 10 + agg["M"]

    def segment(row):
        r, f, m = row["R"], row["F"], row["M"]
        if r >= 4 and f >= 4 and m >= 4:
            return "⭐ Champion"
        if r >= 3 and f >= 3:
            return "💚 Loyal"
        if r >= 4 and f <= 2:
            return "🌱 Promising"
        if r <= 2 and f >= 3 and m >= 3:
            return "⚠️ At Risk"
        if r <= 2 and m >= 4:
            return "🚨 Can't Lose"
        if f == 1:
            return "1️⃣ One-Time"
        if r == 1:
            return "💤 Lapsed"
        return "➡️ Regular"

    agg["Segment"] = agg.apply(segment, axis=1)
    return agg.sort_values("TotalSpend", ascending=False)


def top_clients(trip_clients: pd.DataFrame, bookings: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Return top N clients by total billed revenue."""
    if trip_clients.empty or bookings.empty:
        return pd.DataFrame()

    # Confirmed bookings with revenue
    rev = bookings[bookings[REVENUE_FIELD].notna()][["Trip__c", REVENUE_FIELD]].copy()
    rev = rev.groupby("Trip__c")[REVENUE_FIELD].sum().reset_index()

    clean_clients = _clean_clients(trip_clients.copy())

    # Join to trip-client (lead clients only to avoid double-counting)
    leads = clean_clients[clean_clients.get("Lead_Client__c", False) == True].copy() \
        if "Lead_Client__c" in clean_clients.columns else clean_clients.copy()
    if leads.empty:
        leads = clean_clients.copy()

    merged = leads.merge(rev, on="Trip__c", how="inner")
    client_col = "Client_Name" if "Client_Name" in merged.columns else "Client__c"
    if client_col not in merged.columns:
        return pd.DataFrame()

    top = (
        merged.groupby(client_col)[REVENUE_FIELD]
        .sum()
        .reset_index()
        .rename(columns={client_col: "Client", REVENUE_FIELD: "Revenue_GBP"})
        .sort_values("Revenue_GBP", ascending=False)
        .head(n)
    )
    return top
