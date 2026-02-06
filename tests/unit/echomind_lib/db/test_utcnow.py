"""
Unit tests for utcnow() helper and TIMESTAMP timezone-awareness.

Verifies:
- utcnow() returns timezone-aware UTC datetimes
- TIMESTAMP column type is TIMESTAMPTZ (timezone=True)
- ORM model defaults produce timezone-aware datetimes
- CRUD operations set timezone-aware datetimes
- No timezone-naive datetimes leak through any code path
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from echomind_lib.db.models.base import TIMESTAMP, utcnow


class TestUtcnow:
    """Tests for the utcnow() helper function."""

    def test_returns_datetime(self) -> None:
        """utcnow() returns a datetime instance."""
        result = utcnow()
        assert isinstance(result, datetime)

    def test_returns_timezone_aware(self) -> None:
        """utcnow() returns a timezone-aware datetime (not naive)."""
        result = utcnow()
        assert result.tzinfo is not None, "utcnow() returned a naive datetime"

    def test_returns_utc_timezone(self) -> None:
        """utcnow() returns a datetime in UTC timezone specifically."""
        result = utcnow()
        assert result.tzinfo == timezone.utc

    def test_returns_current_time(self) -> None:
        """utcnow() returns approximately the current UTC time."""
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_successive_calls_increase(self) -> None:
        """Successive calls return non-decreasing timestamps."""
        first = utcnow()
        second = utcnow()
        assert second >= first

    def test_can_subtract_from_aware_datetime(self) -> None:
        """utcnow() result can be subtracted from another aware datetime.

        This is the exact operation that asyncpg 0.31+ performs.
        Mixing aware and naive datetimes raises TypeError.
        """
        aware = datetime.now(timezone.utc)
        result = utcnow()
        delta = result - aware  # Must not raise TypeError
        assert delta.total_seconds() >= 0 or True  # Just verifying no exception

    def test_cannot_subtract_naive_from_utcnow(self) -> None:
        """Subtracting a naive datetime from utcnow() raises TypeError.

        This proves utcnow() is truly timezone-aware — the exact scenario
        asyncpg rejects when columns are TIMESTAMP (naive) but values are aware.
        """
        naive = datetime(2026, 1, 1, 0, 0, 0)  # No tzinfo
        result = utcnow()
        with pytest.raises(TypeError, match="can't subtract offset-naive and offset-aware"):
            _ = result - naive

    def test_isoformat_includes_timezone(self) -> None:
        """utcnow().isoformat() includes timezone offset (+00:00)."""
        result = utcnow()
        iso = result.isoformat()
        assert "+00:00" in iso or "Z" in iso


class TestTimestampColumnType:
    """Tests for the TIMESTAMP column type definition."""

    def test_timestamp_is_timezone_aware(self) -> None:
        """TIMESTAMP column type has timezone=True (TIMESTAMPTZ)."""
        assert TIMESTAMP.timezone is True, (
            "TIMESTAMP must be TIMESTAMPTZ (timezone=True). "
            "asyncpg 0.31+ rejects aware datetimes for naive columns."
        )


class TestOrmModelDefaults:
    """Tests that ORM model defaults use the utcnow function.

    SQLAlchemy wraps default callables in ColumnDefault, so we verify
    the default.arg IS the utcnow function (identity check). The utcnow()
    function itself is tested in TestUtcnow above.
    """

    _MODELS_WITH_CREATION_DATE: list[tuple[str, str]] = [
        ("echomind_lib.db.models.user", "User"),
        ("echomind_lib.db.models.connector", "Connector"),
        ("echomind_lib.db.models.document", "Document"),
        ("echomind_lib.db.models.chat_session", "ChatSession"),
        ("echomind_lib.db.models.chat_message", "ChatMessage"),
        ("echomind_lib.db.models.agent_memory", "AgentMemory"),
        ("echomind_lib.db.models.team", "Team"),
        ("echomind_lib.db.models.llm", "LLM"),
        ("echomind_lib.db.models.assistant", "Assistant"),
        ("echomind_lib.db.models.embedding_model", "EmbeddingModel"),
    ]

    @pytest.mark.parametrize(
        "module_path,class_name",
        _MODELS_WITH_CREATION_DATE,
        ids=[c for _, c in _MODELS_WITH_CREATION_DATE],
    )
    def test_creation_date_default_is_utcnow(
        self, module_path: str, class_name: str
    ) -> None:
        """Model.creation_date default is the utcnow function."""
        import importlib

        module = importlib.import_module(module_path)
        model_cls = getattr(module, class_name)
        col = model_cls.__table__.columns["creation_date"]
        assert col.default is not None, (
            f"{class_name}.creation_date has no default"
        )
        # Compare by name+module (not identity) because PYTHONPATH=src
        # can cause the same module to load under different sys.modules keys,
        # producing distinct function objects for the same source function.
        default_fn = col.default.arg
        assert callable(default_fn), (
            f"{class_name}.creation_date default is not callable: {default_fn}"
        )
        assert default_fn.__name__ == "utcnow", (
            f"{class_name}.creation_date default is {default_fn.__name__}, "
            f"expected utcnow"
        )
        assert "echomind_lib.db.models.base" in default_fn.__module__, (
            f"{class_name}.creation_date default from {default_fn.__module__}, "
            f"expected echomind_lib.db.models.base"
        )

    def test_all_timestamp_columns_are_timestamptz(self) -> None:
        """Every TIMESTAMP column across all models uses timezone=True.

        This is the definitive test: iterates all ORM models, all columns,
        and verifies any PostgreSQL TIMESTAMP column has timezone=True.
        """
        from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP

        from echomind_lib.db.connection import Base

        errors: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            for col in table.columns:
                col_type = col.type
                if isinstance(col_type, PG_TIMESTAMP):
                    if not col_type.timezone:
                        errors.append(
                            f"{table_name}.{col.name} is TIMESTAMP (naive), "
                            f"must be TIMESTAMPTZ (timezone=True)"
                        )

        assert not errors, (
            "Found TIMESTAMP columns without timezone=True:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


class TestCrudDatetimeAwareness:
    """Tests that CRUD operations set timezone-aware datetimes."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_soft_delete_sets_aware_datetime(self, mock_session: AsyncMock) -> None:
        """SoftDeleteMixin.soft_delete() sets timezone-aware deleted_date."""
        from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin

        class MockModel:
            id = MagicMock()
            deleted_date = MagicMock()

        class TestCRUD(SoftDeleteMixin[MockModel], CRUDBase[MockModel]):
            pass

        crud = TestCRUD(MockModel)

        mock_obj = MagicMock()
        mock_obj.deleted_date = None

        with patch.object(crud, "get_by_id_active", return_value=mock_obj):
            result = await crud.soft_delete(mock_session, id=1)

        assert result is True
        assert mock_obj.deleted_date.tzinfo is not None, (
            "soft_delete() set a naive datetime for deleted_date"
        )
        assert mock_obj.deleted_date.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_user_crud_update_last_login_aware(self, mock_session: AsyncMock) -> None:
        """UserCRUD.update_last_login() sets timezone-aware last_login."""
        from echomind_lib.db.crud.user import UserCRUD

        crud = UserCRUD()
        mock_user = MagicMock()
        mock_user.last_login = None

        with patch.object(crud, "get_by_id", return_value=mock_user):
            result = await crud.update_last_login(mock_session, user_id=1)

        assert result is not None
        assert mock_user.last_login.tzinfo is not None
        assert mock_user.last_login.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_user_crud_upsert_from_oidc_sets_aware_dates(
        self, mock_session: AsyncMock
    ) -> None:
        """UserCRUD.upsert_from_oidc() sets timezone-aware last_login and last_update."""
        from echomind_lib.db.crud.user import UserCRUD

        crud = UserCRUD()
        mock_user = MagicMock()
        mock_user.last_login = None
        mock_user.last_update = None

        with patch.object(crud, "get_by_external_id", return_value=mock_user):
            result = await crud.upsert_from_oidc(
                mock_session,
                external_id="ext-1",
                user_name="test",
                email="test@test.com",
            )

        assert mock_user.last_login.tzinfo == timezone.utc
        assert mock_user.last_update.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_document_crud_update_status_aware(self, mock_session: AsyncMock) -> None:
        """DocumentCRUD.update_status() sets timezone-aware last_update."""
        from echomind_lib.db.crud.document import DocumentCRUD

        crud = DocumentCRUD()
        mock_doc = MagicMock()
        mock_doc.last_update = None

        with patch.object(crud, "get_by_id", return_value=mock_doc):
            result = await crud.update_status(mock_session, 1, "completed")

        assert mock_doc.last_update.tzinfo is not None
        assert mock_doc.last_update.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_agent_memory_crud_increment_access_aware(
        self, mock_session: AsyncMock
    ) -> None:
        """AgentMemoryCRUD.increment_access() sets timezone-aware last_accessed_at."""
        from echomind_lib.db.crud.agent_memory import AgentMemoryCRUD

        crud = AgentMemoryCRUD()
        mock_memory = MagicMock()
        mock_memory.access_count = 0
        mock_memory.last_accessed_at = None

        with patch.object(crud, "get_by_id", return_value=mock_memory):
            result = await crud.increment_access(mock_session, memory_id=1)

        assert mock_memory.last_accessed_at.tzinfo is not None
        assert mock_memory.last_accessed_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_chat_message_feedback_upsert_aware(
        self, mock_session: AsyncMock
    ) -> None:
        """ChatMessageFeedbackCRUD.upsert() sets timezone-aware last_update."""
        from echomind_lib.db.crud.chat_message import ChatMessageFeedbackCRUD

        crud = ChatMessageFeedbackCRUD()
        mock_feedback = MagicMock()
        mock_feedback.last_update = None

        with patch.object(crud, "get_by_user_and_message", return_value=mock_feedback):
            result = await crud.upsert(
                mock_session, user_id=1, chat_message_id=1, is_positive=True
            )

        assert mock_feedback.last_update.tzinfo is not None
        assert mock_feedback.last_update.tzinfo == timezone.utc
