PAGE_TITLE = "Company Crossing — Travel Analytics"
PAGE_ICON = "✈️"
LAYOUT = "wide"

COLOR_PRIMARY = "#1f77b4"
COLOR_POSITIVE = "#2ca02c"
COLOR_NEGATIVE = "#d62728"
COLOR_NEUTRAL = "#7f7f7f"
COLOR_SEQUENCE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#bcbd22",
]

# Booking_Status__c values that count as active/confirmed revenue
CONFIRMED_STATUSES = ["Confirmed"]

# Trip Status__c values that count as completed/active (not declined/cancelled)
ACTIVE_TRIP_STATUSES = ["✅Completed", "Confirmed", "On-Trip", "Working", "Awaiting Reply"]

# Primary financial fields (GBP — most populated)
REVENUE_FIELD = "Billed_Amount_GBP__c"        # ~2,322 bookings populated
VENDOR_COST_FIELD = "Vendor_Payment_Amount_GBP__c"
COMMISSION_FIELD = "Commission_from_Vendor__c"  # percent

# Supplier account types (used to filter hotels/tours from customer accounts)
SUPPLIER_TYPES = ["Hotel", "Tours", "Tour", "Cruise", "Airline", "Transport", "Car Hire", "Other"]
