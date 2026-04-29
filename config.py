PAGE_TITLE = "Company Crossing — Travel Analytics"
PAGE_ICON = "✈️"
LAYOUT = "wide"

COLOR_PRIMARY = "#7B4F3A"   # warm terracotta-brown
COLOR_POSITIVE = "#4A7C5C"  # muted sage green
COLOR_NEGATIVE = "#C4614A"  # warm terracotta red
COLOR_NEUTRAL = "#8C7B70"   # warm greige
COLOR_SEQUENCE = [
    "#7B4F3A",  # terracotta brown
    "#C4714A",  # warm terracotta
    "#D4A853",  # warm gold
    "#4A7C5C",  # sage green
    "#3D7A7A",  # deep teal
    "#6B8F71",  # muted green
    "#C4857A",  # dusty rose
    "#3D4F6E",  # warm navy
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
