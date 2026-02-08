"""
Base imports and common types for SQLAlchemy ORM models.

This module provides shared imports to avoid circular dependencies.
All timestamp columns use TIMESTAMPTZ (timezone-aware) and utcnow() default.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PG_TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind_lib.db.connection import Base

# All timestamp columns must be timezone-aware (TIMESTAMPTZ)
TIMESTAMP = _PG_TIMESTAMP(timezone=True)


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime.

    Returns:
        Timezone-aware UTC datetime. Use this instead of datetime.utcnow()
        which is deprecated in Python 3.12.
    """
    return datetime.now(timezone.utc)


__all__ = [
    "Base",
    "Mapped",
    "mapped_column",
    "relationship",
    "ForeignKey",
    "Integer",
    "SmallInteger",
    "BigInteger",
    "String",
    "Text",
    "Boolean",
    "Numeric",
    "ARRAY",
    "JSONB",
    "TIMESTAMP",
    "UniqueConstraint",
    "datetime",
    "timezone",
    "utcnow",
    "Any",
    "TYPE_CHECKING",
]
