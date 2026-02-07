"""Shared Google API utilities for all Google connector providers."""

from connector.logic.providers.google_utils.auth import GoogleAuthHelper
from connector.logic.providers.google_utils.markdown import (
    calendar_event_to_markdown,
    contact_to_markdown,
    gmail_thread_to_markdown,
    slugify,
)
from connector.logic.providers.google_utils.pagination import google_paginate
from connector.logic.providers.google_utils.rate_limiter import handle_rate_limit
from echomind_lib.google import (
    GOOGLE_SCOPES,
    all_scopes,
    scopes_for_service,
)

__all__ = [
    "GoogleAuthHelper",
    "GOOGLE_SCOPES",
    "all_scopes",
    "calendar_event_to_markdown",
    "contact_to_markdown",
    "gmail_thread_to_markdown",
    "google_paginate",
    "handle_rate_limit",
    "scopes_for_service",
    "slugify",
]
