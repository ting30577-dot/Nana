"""Nana vNext Python sidecar.

The package is intentionally isolated from the v0.2.0-alpha repositories.
No vNext command writes through the legacy database layer.
"""

APP_VERSION = "0.3.0-dev"
API_VERSION = "1"
SCHEMA_VERSION = 7
SCHEMA_READ_CEILING = 7

__all__ = [
    "API_VERSION",
    "APP_VERSION",
    "SCHEMA_READ_CEILING",
    "SCHEMA_VERSION",
]
