"""
SQLAlchemy ORM models for all EchoMind database tables.

These models map directly to the schema defined in src/db-schema/schema.sql.

Usage:
    from echomind_lib.db.models import User, Assistant, Connector
"""

from echomind_lib.db.models.agent_memory import AgentMemory
from echomind_lib.db.models.assistant import Assistant
from echomind_lib.db.models.chat_message import (
    ChatMessage,
    ChatMessageDocument,
    ChatMessageFeedback,
)
from echomind_lib.db.models.chat_session import ChatSession
from echomind_lib.db.models.connector import Connector
from echomind_lib.db.models.google_credential import GoogleCredential
from echomind_lib.db.models.document import Document
from echomind_lib.db.models.embedding_model import EmbeddingModel
from echomind_lib.db.models.llm import LLM
from echomind_lib.db.models.team import Team, TeamMember
from echomind_lib.db.models.user import User

__all__ = [
    "User",
    "Team",
    "TeamMember",
    "LLM",
    "EmbeddingModel",
    "Assistant",
    "Connector",
    "GoogleCredential",
    "Document",
    "ChatSession",
    "ChatMessage",
    "ChatMessageFeedback",
    "ChatMessageDocument",
    "AgentMemory",
]
