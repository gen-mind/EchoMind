"""
Google OAuth2 scope definitions for all Google services.

Shared across API and Connector services for Google Workspace integration.
"""

from __future__ import annotations


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
    """
    Return OAuth2 scopes for a specific Google service.

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
    """
    Return all Google OAuth2 scopes combined.

    Returns:
        Flat list of all scope URIs across all services.
    """
    return [scope for scopes in GOOGLE_SCOPES.values() for scope in scopes]


def service_has_scopes(service: str, granted_scopes: list[str]) -> bool:
    """
    Check if all required scopes for a service are granted.

    Args:
        service: Service name (drive, gmail, calendar, contacts).
        granted_scopes: List of currently granted scope URIs.

    Returns:
        True if all required scopes for the service are in granted_scopes.

    Raises:
        ValueError: If service is not recognized.
    """
    required = scopes_for_service(service)
    granted_set = set(granted_scopes)
    return all(scope in granted_set for scope in required)


def services_authorized(granted_scopes: list[str]) -> dict[str, bool]:
    """
    Return authorization status for each Google service.

    Args:
        granted_scopes: List of currently granted scope URIs.

    Returns:
        Dict mapping service name to whether all required scopes are granted.
    """
    return {
        service: service_has_scopes(service, granted_scopes)
        for service in GOOGLE_SCOPES
    }
