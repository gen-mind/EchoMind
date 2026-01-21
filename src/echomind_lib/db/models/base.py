"""
Base imports and common types for SQLAlchemy ORM models.

This module provides shared imports to avoid circular dependencies.
"""

from datetime import datetime
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind_lib.db.connection import Base

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
    "Any",
    "TYPE_CHECKING",
]
