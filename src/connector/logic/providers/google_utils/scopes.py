"""Google OAuth2 scope definitions for all Google services."""


# Per-service scope definitions
GOOGLE_SCOPES: dict[str, list[str]] = {
    "drive": [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar.readonly",
    ],
    "contacts": [
        "https://www.googleapis.com/auth/contacts.readonly",
    ],
}


def scopes_for_service(service: str) -> list[str]:
    """Return OAuth2 scopes for a specific Google service.

    Args:
        service: Service name (drive, gmail, calendar, contacts).

    Returns:
        List of scope URIs.

    Raises:
        ValueError: If service is not recognized.
    """
    if service not in GOOGLE_SCOPES:
        raise ValueError(
            f"Unknown Google service: {service}. "
            f"Valid services: {list(GOOGLE_SCOPES.keys())}"
        )
    return GOOGLE_SCOPES[service]


def all_scopes() -> list[str]:
    """Return all Google OAuth2 scopes combined.

    Returns:
        Flat list of all scope URIs across all services.
    """
    return [scope for scopes in GOOGLE_SCOPES.values() for scope in scopes]
