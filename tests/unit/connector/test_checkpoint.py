"""Unit tests for checkpoint models."""

from datetime import datetime, timezone

import pytest

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    DriveRetrievalStage,
    GmailCheckpoint,
    GoogleCalendarCheckpoint,
    GoogleContactsCheckpoint,
    GoogleDriveCheckpoint,
    SharePointCheckpoint,
    SiteDescriptor,
    StageCompletion,
    deserialize_checkpoint,
    serialize_checkpoint,
)


class TestConnectorCheckpoint:
    """Tests for base ConnectorCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = ConnectorCheckpoint()

        assert checkpoint.has_more is True
        assert checkpoint.last_sync_start is None
        assert checkpoint.error_count == 0
        assert checkpoint.documents_processed == 0

    def test_can_set_values(self) -> None:
        """Test setting checkpoint values."""
        now = datetime.now(timezone.utc)
        checkpoint = ConnectorCheckpoint(
            has_more=False,
            last_sync_start=now,
            error_count=5,
            documents_processed=100,
        )

        assert checkpoint.has_more is False
        assert checkpoint.last_sync_start == now
        assert checkpoint.error_count == 5
        assert checkpoint.documents_processed == 100


class TestDriveRetrievalStage:
    """Tests for DriveRetrievalStage enum."""

    def test_all_stages_exist(self) -> None:
        """Test all expected stages exist."""
        stages = [
            DriveRetrievalStage.START,
            DriveRetrievalStage.USER_EMAILS,
            DriveRetrievalStage.MY_DRIVE_FILES,
            DriveRetrievalStage.DRIVE_IDS,
            DriveRetrievalStage.SHARED_DRIVE_FILES,
            DriveRetrievalStage.FOLDER_FILES,
            DriveRetrievalStage.DONE,
        ]

        assert len(stages) == 7

    def test_stages_are_strings(self) -> None:
        """Test stages have string values."""
        assert DriveRetrievalStage.START.value == "start"
        assert DriveRetrievalStage.DONE.value == "done"


class TestStageCompletion:
    """Tests for StageCompletion model."""

    def test_default_values(self) -> None:
        """Test default completion values."""
        completion = StageCompletion(stage=DriveRetrievalStage.START)

        assert completion.stage == DriveRetrievalStage.START
        assert completion.completed_until == 0.0
        assert completion.current_folder_or_drive_id is None
        assert completion.next_page_token is None
        assert completion.processed_drive_ids == set()

    def test_can_track_progress(self) -> None:
        """Test tracking progress through stage."""
        completion = StageCompletion(
            stage=DriveRetrievalStage.MY_DRIVE_FILES,
            completed_until=1234567890.0,
            next_page_token="token123",
        )

        assert completion.completed_until == 1234567890.0
        assert completion.next_page_token == "token123"


class TestGoogleDriveCheckpoint:
    """Tests for GoogleDriveCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = GoogleDriveCheckpoint()

        assert checkpoint.completion_stage == DriveRetrievalStage.START
        assert checkpoint.completion_map == {}
        assert checkpoint.all_retrieved_file_ids == set()
        assert checkpoint.changes_start_page_token is None

    def test_get_user_completion_creates_new(self) -> None:
        """Test get_user_completion creates new entry."""
        checkpoint = GoogleDriveCheckpoint()

        completion = checkpoint.get_user_completion("user@example.com")

        assert "user@example.com" in checkpoint.completion_map
        assert completion.stage == DriveRetrievalStage.START

    def test_get_user_completion_returns_existing(self) -> None:
        """Test get_user_completion returns existing entry."""
        checkpoint = GoogleDriveCheckpoint()
        completion1 = checkpoint.get_user_completion("user@example.com")
        completion1.stage = DriveRetrievalStage.MY_DRIVE_FILES

        completion2 = checkpoint.get_user_completion("user@example.com")

        assert completion2.stage == DriveRetrievalStage.MY_DRIVE_FILES

    def test_mark_file_retrieved_new_file(self) -> None:
        """Test marking new file as retrieved."""
        checkpoint = GoogleDriveCheckpoint()

        result = checkpoint.mark_file_retrieved("file123")

        assert result is True
        assert "file123" in checkpoint.all_retrieved_file_ids
        assert checkpoint.documents_processed == 1

    def test_mark_file_retrieved_duplicate(self) -> None:
        """Test marking duplicate file returns False."""
        checkpoint = GoogleDriveCheckpoint()
        checkpoint.mark_file_retrieved("file123")

        result = checkpoint.mark_file_retrieved("file123")

        assert result is False
        assert checkpoint.documents_processed == 1  # Not incremented


class TestSiteDescriptor:
    """Tests for SiteDescriptor model."""

    def test_stores_site_info(self) -> None:
        """Test site descriptor stores information."""
        site = SiteDescriptor(
            site_id="site123",
            site_name="Engineering",
            site_url="https://company.sharepoint.com/sites/engineering",
        )

        assert site.site_id == "site123"
        assert site.site_name == "Engineering"
        assert site.site_url == "https://company.sharepoint.com/sites/engineering"


class TestSharePointCheckpoint:
    """Tests for SharePointCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = SharePointCheckpoint()

        assert checkpoint.cached_site_descriptors == []
        assert checkpoint.current_site_descriptor is None
        assert checkpoint.cached_drive_names == []
        assert checkpoint.current_drive_name is None
        assert checkpoint.delta_link is None

    def test_pop_next_site_returns_site(self) -> None:
        """Test popping next site from queue."""
        checkpoint = SharePointCheckpoint()
        site = SiteDescriptor(
            site_id="site1", site_name="Site 1", site_url="https://example.com"
        )
        checkpoint.cached_site_descriptors = [site]

        result = checkpoint.pop_next_site()

        assert result == site
        assert checkpoint.current_site_descriptor == site
        assert len(checkpoint.cached_site_descriptors) == 0

    def test_pop_next_site_empty_returns_none(self) -> None:
        """Test popping from empty queue returns None."""
        checkpoint = SharePointCheckpoint()

        result = checkpoint.pop_next_site()

        assert result is None

    def test_pop_next_drive_returns_drive(self) -> None:
        """Test popping next drive from queue."""
        checkpoint = SharePointCheckpoint()
        checkpoint.cached_drive_names = ["Documents", "Shared"]

        result = checkpoint.pop_next_drive()

        assert result == "Documents"
        assert checkpoint.current_drive_name == "Documents"
        assert len(checkpoint.cached_drive_names) == 1

    def test_mark_item_retrieved_new_item(self) -> None:
        """Test marking new item as retrieved."""
        checkpoint = SharePointCheckpoint()

        result = checkpoint.mark_item_retrieved("item123")

        assert result is True
        assert "item123" in checkpoint.all_retrieved_item_ids
        assert checkpoint.documents_processed == 1

    def test_mark_item_retrieved_duplicate(self) -> None:
        """Test marking duplicate item returns False."""
        checkpoint = SharePointCheckpoint()
        checkpoint.mark_item_retrieved("item123")

        result = checkpoint.mark_item_retrieved("item123")

        assert result is False


class TestGmailCheckpoint:
    """Tests for GmailCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = GmailCheckpoint()

        assert checkpoint.history_id is None
        assert checkpoint.page_token is None
        assert checkpoint.last_full_sync_at is None
        assert checkpoint.all_retrieved_thread_ids == set()

    def test_mark_thread_retrieved_new(self) -> None:
        """Test marking new thread as retrieved."""
        checkpoint = GmailCheckpoint()

        result = checkpoint.mark_thread_retrieved("thread123")

        assert result is True
        assert "thread123" in checkpoint.all_retrieved_thread_ids
        assert checkpoint.documents_processed == 1

    def test_mark_thread_retrieved_duplicate(self) -> None:
        """Test marking duplicate thread returns False."""
        checkpoint = GmailCheckpoint()
        checkpoint.mark_thread_retrieved("thread123")

        result = checkpoint.mark_thread_retrieved("thread123")

        assert result is False
        assert checkpoint.documents_processed == 1


class TestGoogleCalendarCheckpoint:
    """Tests for GoogleCalendarCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = GoogleCalendarCheckpoint()

        assert checkpoint.sync_tokens == {}
        assert checkpoint.calendar_ids is None
        assert checkpoint.current_calendar_idx == 0
        assert checkpoint.page_token is None

    def test_can_set_values(self) -> None:
        """Test setting checkpoint values."""
        checkpoint = GoogleCalendarCheckpoint(
            sync_tokens={"primary": "sync_tok_1", "work@example.com": "sync_tok_2"},
            calendar_ids=["primary", "work@example.com"],
            current_calendar_idx=1,
            page_token="page_tok_1",
        )

        assert checkpoint.sync_tokens == {"primary": "sync_tok_1", "work@example.com": "sync_tok_2"}
        assert checkpoint.calendar_ids == ["primary", "work@example.com"]
        assert checkpoint.current_calendar_idx == 1
        assert checkpoint.page_token == "page_tok_1"


class TestGoogleContactsCheckpoint:
    """Tests for GoogleContactsCheckpoint."""

    def test_default_values(self) -> None:
        """Test default checkpoint values."""
        checkpoint = GoogleContactsCheckpoint()

        assert checkpoint.sync_token is None
        assert checkpoint.page_token is None

    def test_can_set_values(self) -> None:
        """Test setting checkpoint values."""
        checkpoint = GoogleContactsCheckpoint(
            sync_token="contacts_sync_tok",
            page_token="contacts_page_tok",
        )

        assert checkpoint.sync_token == "contacts_sync_tok"
        assert checkpoint.page_token == "contacts_page_tok"


class TestSerialization:
    """Tests for checkpoint serialization."""

    def test_serialize_base_checkpoint(self) -> None:
        """Test serializing base checkpoint."""
        checkpoint = ConnectorCheckpoint(
            has_more=False,
            documents_processed=50,
        )

        data = serialize_checkpoint(checkpoint)

        assert data["_type"] == "ConnectorCheckpoint"
        assert data["has_more"] is False
        assert data["documents_processed"] == 50

    def test_serialize_google_drive_checkpoint(self) -> None:
        """Test serializing Google Drive checkpoint."""
        checkpoint = GoogleDriveCheckpoint(
            completion_stage=DriveRetrievalStage.MY_DRIVE_FILES,
            changes_start_page_token="token123",
        )

        data = serialize_checkpoint(checkpoint)

        assert data["_type"] == "GoogleDriveCheckpoint"
        assert data["completion_stage"] == "my_drive_files"
        assert data["changes_start_page_token"] == "token123"

    def test_deserialize_base_checkpoint(self) -> None:
        """Test deserializing base checkpoint."""
        data = {
            "_type": "ConnectorCheckpoint",
            "has_more": False,
            "documents_processed": 100,
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, ConnectorCheckpoint)
        assert checkpoint.has_more is False
        assert checkpoint.documents_processed == 100

    def test_deserialize_google_drive_checkpoint(self) -> None:
        """Test deserializing Google Drive checkpoint."""
        data = {
            "_type": "GoogleDriveCheckpoint",
            "completion_stage": "my_drive_files",
            "changes_start_page_token": "token123",
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, GoogleDriveCheckpoint)
        assert checkpoint.completion_stage == DriveRetrievalStage.MY_DRIVE_FILES
        assert checkpoint.changes_start_page_token == "token123"

    def test_deserialize_sharepoint_checkpoint(self) -> None:
        """Test deserializing SharePoint checkpoint."""
        data = {
            "_type": "SharePointCheckpoint",
            "delta_link": "https://graph.microsoft.com/delta?token=abc",
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, SharePointCheckpoint)
        assert checkpoint.delta_link == "https://graph.microsoft.com/delta?token=abc"

    def test_deserialize_unknown_type_raises(self) -> None:
        """Test deserializing unknown type raises error."""
        data = {"_type": "UnknownCheckpoint"}

        with pytest.raises(ValueError, match="Unknown checkpoint type"):
            deserialize_checkpoint(data)

    def test_serialize_gmail_checkpoint(self) -> None:
        """Test serializing Gmail checkpoint."""
        checkpoint = GmailCheckpoint(history_id="12345")

        data = serialize_checkpoint(checkpoint)

        assert data["_type"] == "GmailCheckpoint"
        assert data["history_id"] == "12345"

    def test_deserialize_gmail_checkpoint(self) -> None:
        """Test deserializing Gmail checkpoint."""
        data = {
            "_type": "GmailCheckpoint",
            "history_id": "12345",
            "page_token": "page1",
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, GmailCheckpoint)
        assert checkpoint.history_id == "12345"
        assert checkpoint.page_token == "page1"

    def test_serialize_calendar_checkpoint(self) -> None:
        """Test serializing Calendar checkpoint."""
        checkpoint = GoogleCalendarCheckpoint(
            sync_tokens={"primary": "sync_tok_1", "work": "sync_tok_2"},
            calendar_ids=["primary", "work"],
            current_calendar_idx=1,
        )

        data = serialize_checkpoint(checkpoint)

        assert data["_type"] == "GoogleCalendarCheckpoint"
        assert data["sync_tokens"] == {"primary": "sync_tok_1", "work": "sync_tok_2"}
        assert data["calendar_ids"] == ["primary", "work"]
        assert data["current_calendar_idx"] == 1

    def test_deserialize_calendar_checkpoint(self) -> None:
        """Test deserializing Calendar checkpoint."""
        data = {
            "_type": "GoogleCalendarCheckpoint",
            "sync_tokens": {"primary": "sync_tok"},
            "calendar_ids": ["primary"],
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, GoogleCalendarCheckpoint)
        assert checkpoint.sync_tokens == {"primary": "sync_tok"}
        assert checkpoint.calendar_ids == ["primary"]

    def test_serialize_contacts_checkpoint(self) -> None:
        """Test serializing Contacts checkpoint."""
        checkpoint = GoogleContactsCheckpoint(sync_token="contacts_tok")

        data = serialize_checkpoint(checkpoint)

        assert data["_type"] == "GoogleContactsCheckpoint"
        assert data["sync_token"] == "contacts_tok"

    def test_deserialize_contacts_checkpoint(self) -> None:
        """Test deserializing Contacts checkpoint."""
        data = {
            "_type": "GoogleContactsCheckpoint",
            "sync_token": "contacts_tok",
            "page_token": "page2",
        }

        checkpoint = deserialize_checkpoint(data)

        assert isinstance(checkpoint, GoogleContactsCheckpoint)
        assert checkpoint.sync_token == "contacts_tok"
        assert checkpoint.page_token == "page2"

    def test_roundtrip_serialization(self) -> None:
        """Test checkpoint survives serialize/deserialize roundtrip."""
        original = GoogleDriveCheckpoint(
            has_more=False,
            completion_stage=DriveRetrievalStage.DONE,
            documents_processed=500,
            changes_start_page_token="page_token",
        )
        original.all_retrieved_file_ids.add("file1")
        original.all_retrieved_file_ids.add("file2")

        data = serialize_checkpoint(original)
        restored = deserialize_checkpoint(data)

        assert isinstance(restored, GoogleDriveCheckpoint)
        assert restored.has_more == original.has_more
        assert restored.completion_stage == original.completion_stage
        assert restored.documents_processed == original.documents_processed
        assert restored.changes_start_page_token == original.changes_start_page_token

    def test_roundtrip_gmail_checkpoint(self) -> None:
        """Test Gmail checkpoint roundtrip."""
        original = GmailCheckpoint(
            history_id="99999",
            documents_processed=42,
        )
        original.all_retrieved_thread_ids.add("t1")

        data = serialize_checkpoint(original)
        restored = deserialize_checkpoint(data)

        assert isinstance(restored, GmailCheckpoint)
        assert restored.history_id == "99999"
        assert restored.documents_processed == 42

    def test_roundtrip_calendar_checkpoint(self) -> None:
        """Test Calendar checkpoint roundtrip."""
        original = GoogleCalendarCheckpoint(
            sync_tokens={"primary": "cal_sync"},
            calendar_ids=["primary"],
            current_calendar_idx=0,
        )

        data = serialize_checkpoint(original)
        restored = deserialize_checkpoint(data)

        assert isinstance(restored, GoogleCalendarCheckpoint)
        assert restored.sync_tokens == {"primary": "cal_sync"}
        assert restored.calendar_ids == ["primary"]

    def test_roundtrip_contacts_checkpoint(self) -> None:
        """Test Contacts checkpoint roundtrip."""
        original = GoogleContactsCheckpoint(sync_token="ppl_sync")

        data = serialize_checkpoint(original)
        restored = deserialize_checkpoint(data)

        assert isinstance(restored, GoogleContactsCheckpoint)
        assert restored.sync_token == "ppl_sync"
