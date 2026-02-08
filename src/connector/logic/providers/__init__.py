"""
Connector providers for external data sources.

Each provider handles authentication, change detection,
and file download for a specific data source.
"""

from connector.logic.providers.base import BaseProvider
from connector.logic.providers.google_calendar import GoogleCalendarProvider
from connector.logic.providers.google_contacts import GoogleContactsProvider
from connector.logic.providers.google_drive import GoogleDriveProvider
from connector.logic.providers.google_gmail import GmailProvider
from connector.logic.providers.onedrive import OneDriveProvider

__all__ = [
    "BaseProvider",
    "GmailProvider",
    "GoogleCalendarProvider",
    "GoogleContactsProvider",
    "GoogleDriveProvider",
    "OneDriveProvider",
]
