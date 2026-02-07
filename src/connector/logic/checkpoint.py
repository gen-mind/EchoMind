"""
Checkpoint models for resumable, fault-tolerant syncing.

Checkpoints track sync progress and enable resumption after failures.
Each provider has its own checkpoint type with provider-specific state.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DriveRetrievalStage(str, Enum):
    """Stages for Google Drive retrieval process."""

    START = "start"
    USER_EMAILS = "user_emails"  # Service account: fetch all org users
    MY_DRIVE_FILES = "my_drive_files"  # Each user's personal drive
    DRIVE_IDS = "drive_ids"  # Fetch shared drive IDs
    SHARED_DRIVE_FILES = "shared_drive_files"  # Files from shared drives
    FOLDER_FILES = "folder_files"  # Custom folder crawling
    DONE = "done"


class StageCompletion(BaseModel):
    """Progress within a retrieval stage."""

    model_config = {"arbitrary_types_allowed": True}

    stage: DriveRetrievalStage = Field(
        description="Current stage being processed",
    )
    completed_until: float = Field(
        default=0.0,
        description="Last file modified timestamp (epoch)",
    )
    current_folder_or_drive_id: str | None = Field(
        default=None,
        description="ID of folder/drive currently being processed",
    )
    next_page_token: str | None = Field(
        default=None,
        description="API pagination token for resumption",
    )
    processed_drive_ids: set[str] = Field(
        default_factory=set,
        description="Drive IDs that have been fully processed",
    )


class ConnectorCheckpoint(BaseModel):
    """
    Base checkpoint for all providers.

    All provider-specific checkpoints extend this base class.
    """

    has_more: bool = Field(
        default=True,
        description="Whether more documents remain to retrieve",
    )
    last_sync_start: datetime | None = Field(
        default=None,
        description="When this sync session started",
    )
    error_count: int = Field(
        default=0,
        description="Number of errors encountered during sync",
    )
    documents_processed: int = Field(
        default=0,
        description="Number of documents processed in this session",
    )


class GoogleDriveCheckpoint(ConnectorCheckpoint):
    """
    Multi-stage checkpoint for Google Drive.

    Handles personal drives, shared drives, and folder crawling with
    per-user progress tracking for service account impersonation.
    """

    model_config = {"arbitrary_types_allowed": True}

    # Current retrieval stage
    completion_stage: DriveRetrievalStage = Field(
        default=DriveRetrievalStage.START,
        description="Current stage in the retrieval process",
    )

    # Per-user progress (for service account impersonation)
    completion_map: dict[str, StageCompletion] = Field(
        default_factory=dict,
        description="Progress per user email",
    )

    # Deduplication
    all_retrieved_file_ids: set[str] = Field(
        default_factory=set,
        description="File IDs already retrieved (prevents duplicates)",
    )
    retrieved_folder_and_drive_ids: set[str] = Field(
        default_factory=set,
        description="Folder/drive IDs already crawled",
    )

    # Cached data (fetched once, reused across retries)
    drive_ids_to_retrieve: list[str] | None = Field(
        default=None,
        description="Shared drive IDs to process",
    )
    folder_ids_to_retrieve: list[str] | None = Field(
        default=None,
        description="Folder IDs to crawl",
    )
    user_emails: list[str] | None = Field(
        default=None,
        description="User emails for service account impersonation",
    )

    # Changes API state
    changes_start_page_token: str | None = Field(
        default=None,
        description="Token for incremental sync via Changes API",
    )

    def get_user_completion(self, email: str) -> StageCompletion:
        """
        Get or create completion state for a user.

        Args:
            email: User email address.

        Returns:
            StageCompletion for the user.
        """
        if email not in self.completion_map:
            self.completion_map[email] = StageCompletion(
                stage=DriveRetrievalStage.START
            )
        return self.completion_map[email]

    def mark_file_retrieved(self, file_id: str) -> bool:
        """
        Mark a file as retrieved, returning whether it was new.

        Args:
            file_id: The file ID to mark.

        Returns:
            True if file was newly added, False if already seen.
        """
        if file_id in self.all_retrieved_file_ids:
            return False
        self.all_retrieved_file_ids.add(file_id)
        self.documents_processed += 1
        return True


class SiteDescriptor(BaseModel):
    """Descriptor for a SharePoint site."""

    site_id: str = Field(description="SharePoint site ID")
    site_name: str = Field(description="Human-readable site name")
    site_url: str = Field(description="SharePoint site URL")


class SharePointCheckpoint(ConnectorCheckpoint):
    """
    Deque-based checkpoint for SharePoint/OneDrive.

    Processes sites and drives in FIFO order for fair distribution.
    """

    model_config = {"arbitrary_types_allowed": True}

    # Sites to process (deque for FIFO)
    cached_site_descriptors: list[SiteDescriptor] = Field(
        default_factory=list,
        description="Sites remaining to process (FIFO order)",
    )
    current_site_descriptor: SiteDescriptor | None = Field(
        default=None,
        description="Site currently being processed",
    )

    # Drives within current site
    cached_drive_names: list[str] = Field(
        default_factory=list,
        description="Drives in current site (FIFO order)",
    )
    current_drive_name: str | None = Field(
        default=None,
        description="Drive currently being processed",
    )

    # Delta API state
    delta_link: str | None = Field(
        default=None,
        description="Delta link for incremental sync",
    )

    # Deduplication
    all_retrieved_item_ids: set[str] = Field(
        default_factory=set,
        description="Item IDs already retrieved",
    )

    def pop_next_site(self) -> SiteDescriptor | None:
        """
        Pop the next site to process.

        Returns:
            Next SiteDescriptor or None if queue is empty.
        """
        if self.cached_site_descriptors:
            self.current_site_descriptor = self.cached_site_descriptors.pop(0)
            return self.current_site_descriptor
        return None

    def pop_next_drive(self) -> str | None:
        """
        Pop the next drive to process in current site.

        Returns:
            Next drive name or None if queue is empty.
        """
        if self.cached_drive_names:
            self.current_drive_name = self.cached_drive_names.pop(0)
            return self.current_drive_name
        return None

    def mark_item_retrieved(self, item_id: str) -> bool:
        """
        Mark an item as retrieved, returning whether it was new.

        Args:
            item_id: The item ID to mark.

        Returns:
            True if item was newly added, False if already seen.
        """
        if item_id in self.all_retrieved_item_ids:
            return False
        self.all_retrieved_item_ids.add(item_id)
        self.documents_processed += 1
        return True


class GmailCheckpoint(ConnectorCheckpoint):
    """
    Checkpoint for Gmail incremental sync.

    Uses Gmail History API (historyId) for efficient incremental sync.
    First sync lists all threads, subsequent syncs use history.list.
    """

    model_config = {"arbitrary_types_allowed": True}

    history_id: str | None = Field(
        default=None,
        description="historyId for incremental sync via history.list",
    )
    page_token: str | None = Field(
        default=None,
        description="Current page token during thread listing",
    )
    last_full_sync_at: datetime | None = Field(
        default=None,
        description="When the last full sync completed",
    )

    # Deduplication
    all_retrieved_thread_ids: set[str] = Field(
        default_factory=set,
        description="Thread IDs already retrieved",
    )

    def mark_thread_retrieved(self, thread_id: str) -> bool:
        """
        Mark a thread as retrieved, returning whether it was new.

        Args:
            thread_id: The thread ID to mark.

        Returns:
            True if thread was newly added, False if already seen.
        """
        if thread_id in self.all_retrieved_thread_ids:
            return False
        self.all_retrieved_thread_ids.add(thread_id)
        self.documents_processed += 1
        return True


class GoogleCalendarCheckpoint(ConnectorCheckpoint):
    """
    Checkpoint for Google Calendar incremental sync.

    Uses Calendar API syncToken for efficient incremental sync.
    Each calendar has its own syncToken stored in sync_tokens dict.
    On 410 GONE response, performs a full resync for that calendar.
    """

    sync_tokens: dict[str, str] = Field(
        default_factory=dict,
        description="Per-calendar syncTokens (calendar_id -> syncToken)",
    )
    calendar_ids: list[str] | None = Field(
        default=None,
        description="List of calendar IDs to sync",
    )
    current_calendar_idx: int = Field(
        default=0,
        description="Index into calendar_ids for resumption within a sync cycle",
    )
    page_token: str | None = Field(
        default=None,
        description="Current page token during event listing",
    )


class GoogleContactsCheckpoint(ConnectorCheckpoint):
    """
    Checkpoint for Google Contacts incremental sync.

    Uses People API syncToken for efficient incremental sync.
    syncToken expires after 7 days; on 410 GONE, performs full resync.
    """

    sync_token: str | None = Field(
        default=None,
        description="People API syncToken for incremental sync",
    )
    page_token: str | None = Field(
        default=None,
        description="Current page token during contact listing",
    )


# Type alias for checkpoint serialization
CheckpointData = dict[str, Any]


def serialize_checkpoint(checkpoint: ConnectorCheckpoint) -> CheckpointData:
    """
    Serialize a checkpoint to a dictionary for database storage.

    Args:
        checkpoint: Checkpoint instance to serialize.

    Returns:
        Dictionary representation of the checkpoint.
    """
    data = checkpoint.model_dump(mode="json")
    # Store the checkpoint type for deserialization
    data["_type"] = checkpoint.__class__.__name__
    return data


def deserialize_checkpoint(data: CheckpointData) -> ConnectorCheckpoint:
    """
    Deserialize a checkpoint from database storage.

    Args:
        data: Dictionary from database.

    Returns:
        Checkpoint instance.

    Raises:
        ValueError: If checkpoint type is unknown.
    """
    checkpoint_type = data.pop("_type", None)

    checkpoint_classes: dict[str, type[ConnectorCheckpoint]] = {
        "GoogleDriveCheckpoint": GoogleDriveCheckpoint,
        "SharePointCheckpoint": SharePointCheckpoint,
        "GmailCheckpoint": GmailCheckpoint,
        "GoogleCalendarCheckpoint": GoogleCalendarCheckpoint,
        "GoogleContactsCheckpoint": GoogleContactsCheckpoint,
    }

    if checkpoint_type in checkpoint_classes:
        return checkpoint_classes[checkpoint_type].model_validate(data)
    elif checkpoint_type == "ConnectorCheckpoint" or checkpoint_type is None:
        return ConnectorCheckpoint.model_validate(data)
    else:
        raise ValueError(f"Unknown checkpoint type: {checkpoint_type}")
