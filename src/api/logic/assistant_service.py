"""
Assistant business logic service.

Handles all assistant-related business operations, keeping routes thin.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.logic.exceptions import NotFoundError
from echomind_lib.db.models import Assistant as AssistantORM
from echomind_lib.models.public import (
    Assistant,
    CreateAssistantRequest,
    ListAssistantsResponse,
    UpdateAssistantRequest,
)


class AssistantService:
    """Service for assistant-related business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize AssistantService.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    async def get_by_id(self, assistant_id: int) -> Assistant:
        """
        Get an assistant by ID.

        Args:
            assistant_id: The ID of the assistant to retrieve.

        Returns:
            Assistant: The assistant data.

        Raises:
            NotFoundError: If assistant not found or deleted.
        """
        result = await self.db.execute(
            select(AssistantORM)
            .where(AssistantORM.id == assistant_id)
            .where(AssistantORM.deleted_date.is_(None))
        )
        db_assistant = result.scalar_one_or_none()

        if not db_assistant:
            raise NotFoundError("Assistant", assistant_id)

        return Assistant.model_validate(db_assistant, from_attributes=True)

    async def list_assistants(
        self,
        page: int = 1,
        limit: int = 20,
        is_visible: bool | None = None,
    ) -> ListAssistantsResponse:
        """
        List assistants with pagination.

        Args:
            page: Page number (1-indexed).
            limit: Number of items per page.
            is_visible: Optional filter by visibility.

        Returns:
            ListAssistantsResponse: Paginated list of assistants.
        """
        query = select(AssistantORM).where(AssistantORM.deleted_date.is_(None))

        if is_visible is not None:
            query = query.where(AssistantORM.is_visible == is_visible)

        query = query.order_by(AssistantORM.display_priority, AssistantORM.name)

        # Count total
        count_query = select(AssistantORM.id).where(AssistantORM.deleted_date.is_(None))
        if is_visible is not None:
            count_query = count_query.where(AssistantORM.is_visible == is_visible)
        count_result = await self.db.execute(count_query)
        total = len(count_result.all())

        # Paginate
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        db_assistants = result.scalars().all()

        assistants = [
            Assistant.model_validate(a, from_attributes=True) for a in db_assistants
        ]

        return ListAssistantsResponse(assistants=assistants)

    async def create(
        self,
        data: CreateAssistantRequest,
        created_by_user_id: int,
    ) -> Assistant:
        """
        Create a new assistant.

        Args:
            data: The assistant creation data.
            created_by_user_id: ID of the user creating the assistant.

        Returns:
            Assistant: The created assistant.
        """
        assistant = AssistantORM(
            name=data.name,
            description=data.description,
            llm_id=data.llm_id,
            system_prompt=data.system_prompt,
            task_prompt=data.task_prompt,
            starter_messages=data.starter_messages,
            is_default=data.is_default,
            is_visible=data.is_visible,
            display_priority=data.display_priority,
            created_by=created_by_user_id,
            user_id_last_update=created_by_user_id,
        )

        self.db.add(assistant)
        await self.db.flush()
        await self.db.refresh(assistant)

        return Assistant.model_validate(assistant, from_attributes=True)

    async def update(
        self,
        assistant_id: int,
        data: UpdateAssistantRequest,
        updated_by_user_id: int,
    ) -> Assistant:
        """
        Update an assistant.

        Args:
            assistant_id: The ID of the assistant to update.
            data: The fields to update.
            updated_by_user_id: ID of the user performing the update.

        Returns:
            Assistant: The updated assistant.

        Raises:
            NotFoundError: If assistant not found or deleted.
        """
        result = await self.db.execute(
            select(AssistantORM)
            .where(AssistantORM.id == assistant_id)
            .where(AssistantORM.deleted_date.is_(None))
        )
        db_assistant = result.scalar_one_or_none()

        if not db_assistant:
            raise NotFoundError("Assistant", assistant_id)

        if data.name:
            db_assistant.name = data.name
        if data.description:
            db_assistant.description = data.description
        if data.llm_id:
            db_assistant.llm_id = data.llm_id
        if data.system_prompt:
            db_assistant.system_prompt = data.system_prompt
        if data.task_prompt:
            db_assistant.task_prompt = data.task_prompt
        if data.starter_messages:
            db_assistant.starter_messages = data.starter_messages
        if data.is_default is not None:
            db_assistant.is_default = data.is_default
        if data.is_visible is not None:
            db_assistant.is_visible = data.is_visible
        if data.display_priority is not None:
            db_assistant.display_priority = data.display_priority

        db_assistant.user_id_last_update = updated_by_user_id

        return Assistant.model_validate(db_assistant, from_attributes=True)

    async def delete(
        self,
        assistant_id: int,
        deleted_by_user_id: int,
    ) -> None:
        """
        Soft delete an assistant.

        Args:
            assistant_id: The ID of the assistant to delete.
            deleted_by_user_id: ID of the user performing the deletion.

        Raises:
            NotFoundError: If assistant not found or already deleted.
        """
        result = await self.db.execute(
            select(AssistantORM)
            .where(AssistantORM.id == assistant_id)
            .where(AssistantORM.deleted_date.is_(None))
        )
        db_assistant = result.scalar_one_or_none()

        if not db_assistant:
            raise NotFoundError("Assistant", assistant_id)

        db_assistant.deleted_date = datetime.utcnow()
        db_assistant.user_id_last_update = deleted_by_user_id
