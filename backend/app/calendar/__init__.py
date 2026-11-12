"""Calendar bounded context.

``calendar.domain`` holds the provider-independent value objects and the
iCalendar (RFC 5545) parsing/serialization that *every* calendar backend
ultimately needs, so an adapter that returns raw iCalendar text reuses it
unchanged.  ``calendar.providers`` holds the port and its adapters.
"""
