"""Mailbox bounded context.

``mailbox.domain`` holds provider-independent message value objects and the MIME
parsing that every mail backend ultimately needs.  ``mailbox.providers`` holds
the port and its adapters.  The mailbox is **read-only**: the application can
list and read messages, never send, move, or delete them (see DECISIONS D-026).
"""
