"""
Converters between ORM models and Pydantic proto models.

The ORM stores enum values as strings (e.g., "google_drive", "active"),
but the proto-generated Pydantic models expect enum types. This module
provides conversion functions to bridge the gap.
"""

from typing import Any

from echomind_lib.models.public.connector_model import (
    Connector,
    ConnectorScope,
    ConnectorStatus,
    ConnectorType,
)
from echomind_lib.models.public.document_model import (
    Document,
    DocumentStatus,
)


# Connector type string -> enum mapping
CONNECTOR_TYPE_MAP: dict[str, ConnectorType] = {
    "teams": ConnectorType.CONNECTOR_TYPE_TEAMS,
    "google_drive": ConnectorType.CONNECTOR_TYPE_GOOGLE_DRIVE,
    "gmail": ConnectorType.CONNECTOR_TYPE_GMAIL,
    "google_calendar": ConnectorType.CONNECTOR_TYPE_GOOGLE_CALENDAR,
    "google_contacts": ConnectorType.CONNECTOR_TYPE_GOOGLE_CONTACTS,
    "onedrive": ConnectorType.CONNECTOR_TYPE_ONEDRIVE,
    "web": ConnectorType.CONNECTOR_TYPE_WEB,
    "file": ConnectorType.CONNECTOR_TYPE_FILE,
}

# Connector status string -> enum mapping
CONNECTOR_STATUS_MAP: dict[str, ConnectorStatus] = {
    "pending": ConnectorStatus.CONNECTOR_STATUS_PENDING,
    "syncing": ConnectorStatus.CONNECTOR_STATUS_SYNCING,
    "active": ConnectorStatus.CONNECTOR_STATUS_ACTIVE,
    "error": ConnectorStatus.CONNECTOR_STATUS_ERROR,
    "disabled": ConnectorStatus.CONNECTOR_STATUS_DISABLED,
}

# Connector scope string -> enum mapping
CONNECTOR_SCOPE_MAP: dict[str, ConnectorScope] = {
    "user": ConnectorScope.CONNECTOR_SCOPE_USER,
    "group": ConnectorScope.CONNECTOR_SCOPE_GROUP,
    "org": ConnectorScope.CONNECTOR_SCOPE_ORG,
}

# Document status string -> enum mapping
DOCUMENT_STATUS_MAP: dict[str, DocumentStatus] = {
    "pending": DocumentStatus.DOCUMENT_STATUS_PENDING,
    "processing": DocumentStatus.DOCUMENT_STATUS_PROCESSING,
    "completed": DocumentStatus.DOCUMENT_STATUS_COMPLETED,
    "failed": DocumentStatus.DOCUMENT_STATUS_FAILED,
    "error": DocumentStatus.DOCUMENT_STATUS_FAILED,  # Alias
}


def orm_to_connector(orm_obj: Any) -> Connector:
    """
    Convert a Connector ORM object to a Pydantic Connector model.

    Args:
        orm_obj: The SQLAlchemy ORM Connector object.

    Returns:
        Connector: The Pydantic model with proper enum values.
    """
    return Connector(
        id=orm_obj.id,
        name=orm_obj.name,
        type=CONNECTOR_TYPE_MAP.get(
            orm_obj.type, ConnectorType.CONNECTOR_TYPE_UNSPECIFIED
        ),
        config=orm_obj.config,
        state=orm_obj.state,
        refresh_freq_minutes=orm_obj.refresh_freq_minutes or 0,
        user_id=orm_obj.user_id,
        scope=CONNECTOR_SCOPE_MAP.get(
            orm_obj.scope, ConnectorScope.CONNECTOR_SCOPE_UNSPECIFIED
        ),
        scope_id=orm_obj.scope_id or "",
        status=CONNECTOR_STATUS_MAP.get(
            orm_obj.status, ConnectorStatus.CONNECTOR_STATUS_UNSPECIFIED
        ),
        status_message=orm_obj.status_message or "",
        last_sync_at=orm_obj.last_sync_at,
        docs_analyzed=orm_obj.docs_analyzed or 0,
        creation_date=orm_obj.creation_date,
        last_update=orm_obj.last_update,
    )


def orm_to_document(orm_obj: Any) -> Document:
    """
    Convert a Document ORM object to a Pydantic Document model.

    Args:
        orm_obj: The SQLAlchemy ORM Document object.

    Returns:
        Document: The Pydantic model with proper enum values.
    """
    return Document(
        id=orm_obj.id,
        parent_id=orm_obj.parent_id or 0,
        connector_id=orm_obj.connector_id,
        source_id=orm_obj.source_id,
        url=orm_obj.url or "",
        original_url=orm_obj.original_url or "",
        title=orm_obj.title or "",
        content_type=orm_obj.content_type or "",
        status=DOCUMENT_STATUS_MAP.get(
            orm_obj.status, DocumentStatus.DOCUMENT_STATUS_UNSPECIFIED
        ),
        status_message=orm_obj.status_message or "",
        chunk_count=orm_obj.chunk_count or 0,
        creation_date=orm_obj.creation_date,
        last_update=orm_obj.last_update,
    )
