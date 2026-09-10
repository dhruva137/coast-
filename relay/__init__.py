"""COAST public store-and-forward pairing relay.

Phones POST /ingest here. The laptop console pulls /feed. The phone never
needs a route to the laptop — venue guest Wi-Fi with AP isolation still works.
"""

from .mailbox import (
    DEFAULT_TTL_S,
    FORBIDDEN_DEVICE_KEYS,
    MailboxStore,
)

__all__ = [
    "DEFAULT_TTL_S",
    "FORBIDDEN_DEVICE_KEYS",
    "MailboxStore",
]
