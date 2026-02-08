"""Google Workspace utilities shared across services."""

from echomind_lib.google.scopes import (
    GOOGLE_SCOPES,
    all_scopes,
    scopes_for_service,
    service_has_scopes,
    services_authorized,
)

__all__ = [
    "GOOGLE_SCOPES",
    "all_scopes",
    "scopes_for_service",
    "service_has_scopes",
    "services_authorized",
]
