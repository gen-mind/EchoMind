"""Chat session and message endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.dependencies import CurrentUser, DbSession
from echomind_lib.db.models import Assistant as AssistantORM
from echomind_lib.db.models import ChatMessage as ChatMessageORM
from echomind_lib.db.models import ChatMessageDocument as ChatMessageDocumentORM
from echomind_lib.db.models import ChatMessageFeedback as ChatMessageFeedbackORM
from echomind_lib.db.models import ChatSession as ChatSessionORM
from echomind_lib.models.public import (
    ChatMessage,
    ChatSession,
    CreateChatSessionRequest,
    GetChatSessionResponse,
    GetMessageSourcesResponse,
    ListChatSessionsResponse,
    ListMessagesResponse,
    MessageFeedback,
    MessageSource,
    SubmitFeedbackRequest,
)

router = APIRouter()


@router.get("/sessions", response_model=ListChatSessionsResponse)
async def list_chat_sessions(
    user: CurrentUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
    assistant_id: int | None = None,
) -> ListChatSessionsResponse:
    """
    List chat sessions for the current user.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination.
        limit: Number of items per page.
        assistant_id: Optional filter by assistant.

    Returns:
        ListChatSessionsResponse: Paginated list of chat sessions.
    """
    query = select(ChatSessionORM).where(
        ChatSessionORM.user_id == user.id,
        ChatSessionORM.deleted_date.is_(None),
    )
    
    if assistant_id:
        query = query.where(ChatSessionORM.assistant_id == assistant_id)
    
    query = query.order_by(ChatSessionORM.last_message_at.desc().nullslast())
    
    # Count total
    count_query = select(ChatSessionORM.id).where(
        ChatSessionORM.user_id == user.id,
        ChatSessionORM.deleted_date.is_(None),
    )
    if assistant_id:
        count_query = count_query.where(ChatSessionORM.assistant_id == assistant_id)
    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    db_sessions = result.scalars().all()
    
    sessions = [ChatSession.model_validate(s, from_attributes=True) for s in db_sessions]
    
    return ListChatSessionsResponse(sessions=sessions)


@router.post("/sessions", response_model=ChatSession, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    data: CreateChatSessionRequest,
    user: CurrentUser,
    db: DbSession,
) -> ChatSession:
    """
    Create a new chat session.

    Args:
        data: The chat session creation data.
        user: The authenticated user.
        db: Database session.

    Returns:
        ChatSession: The created chat session.

    Raises:
        HTTPException: 404 if assistant not found.
    """
    # Verify assistant exists
    result = await db.execute(
        select(AssistantORM)
        .where(AssistantORM.id == data.assistant_id)
        .where(AssistantORM.deleted_date.is_(None))
    )
    assistant = result.scalar_one_or_none()
    
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )
    
    session = ChatSessionORM(
        user_id=user.id,
        assistant_id=data.assistant_id,
        title=data.title or "New Chat",
        mode=data.mode,
        user_id_last_update=user.id,
    )
    
    db.add(session)
    await db.flush()
    await db.refresh(session)
    
    return ChatSession.model_validate(session, from_attributes=True)


@router.get("/sessions/{session_id}", response_model=GetChatSessionResponse)
async def get_chat_session(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
    message_limit: int = 50,
) -> GetChatSessionResponse:
    """
    Get a chat session with recent messages.

    Args:
        session_id: The ID of the chat session.
        user: The authenticated user.
        db: Database session.
        message_limit: Maximum number of messages to return.

    Returns:
        GetChatSessionResponse: The session with messages.

    Raises:
        HTTPException: 404 if session not found.
    """
    result = await db.execute(
        select(ChatSessionORM)
        .where(ChatSessionORM.id == session_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    db_session = result.scalar_one_or_none()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Get recent messages
    msg_result = await db.execute(
        select(ChatMessageORM)
        .where(ChatMessageORM.chat_session_id == session_id)
        .order_by(ChatMessageORM.creation_date.desc())
        .limit(message_limit)
    )
    db_messages = list(reversed(msg_result.scalars().all()))
    
    session = ChatSession.model_validate(db_session, from_attributes=True)
    messages = [ChatMessage.model_validate(m, from_attributes=True) for m in db_messages]
    
    return GetChatSessionResponse(session=session, messages=messages)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a chat session (soft delete).

    Args:
        session_id: The ID of the chat session to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if session not found.
    """
    result = await db.execute(
        select(ChatSessionORM)
        .where(ChatSessionORM.id == session_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    db_session = result.scalar_one_or_none()
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    db_session.deleted_date = datetime.now(timezone.utc)
    db_session.user_id_last_update = user.id


@router.get("/sessions/{session_id}/messages", response_model=ListMessagesResponse)
async def list_session_messages(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
    page: int = 1,
    limit: int = 50,
) -> ListMessagesResponse:
    """
    List messages in a chat session (paginated).

    Args:
        session_id: The ID of the chat session.
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination.
        limit: Number of items per page.

    Returns:
        ListMessagesResponse: Paginated list of messages.

    Raises:
        HTTPException: 404 if session not found.
    """
    # Verify session ownership
    session_result = await db.execute(
        select(ChatSessionORM.id)
        .where(ChatSessionORM.id == session_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Get messages
    result = await db.execute(
        select(ChatMessageORM)
        .where(ChatMessageORM.chat_session_id == session_id)
        .order_by(ChatMessageORM.creation_date)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    db_messages = result.scalars().all()
    
    messages = [ChatMessage.model_validate(m, from_attributes=True) for m in db_messages]
    
    return ListMessagesResponse(messages=messages)


@router.get("/messages/{message_id}", response_model=ChatMessage)
async def get_message(
    message_id: int,
    user: CurrentUser,
    db: DbSession,
) -> ChatMessage:
    """
    Get a message by ID.

    Args:
        message_id: The ID of the message.
        user: The authenticated user.
        db: Database session.

    Returns:
        ChatMessage: The requested message.

    Raises:
        HTTPException: 404 if message not found.
    """
    result = await db.execute(
        select(ChatMessageORM)
        .join(ChatSessionORM, ChatMessageORM.chat_session_id == ChatSessionORM.id)
        .where(ChatMessageORM.id == message_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    db_message = result.scalar_one_or_none()
    
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    return ChatMessage.model_validate(db_message, from_attributes=True)


@router.get("/messages/{message_id}/sources", response_model=GetMessageSourcesResponse)
async def get_message_sources(
    message_id: int,
    user: CurrentUser,
    db: DbSession,
) -> GetMessageSourcesResponse:
    """
    Get source documents for a message.

    Args:
        message_id: The ID of the message.
        user: The authenticated user.
        db: Database session.

    Returns:
        GetMessageSourcesResponse: List of source documents.

    Raises:
        HTTPException: 404 if message not found.
    """
    # Verify message ownership
    msg_result = await db.execute(
        select(ChatMessageORM.id)
        .join(ChatSessionORM, ChatMessageORM.chat_session_id == ChatSessionORM.id)
        .where(ChatMessageORM.id == message_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    if not msg_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Get sources
    result = await db.execute(
        select(ChatMessageDocumentORM)
        .where(ChatMessageDocumentORM.chat_message_id == message_id)
        .order_by(ChatMessageDocumentORM.relevance_score.desc().nullslast())
    )
    docs = result.scalars().all()
    
    sources = [
        MessageSource(
            document_id=d.document_id,
            chunk_id=d.chunk_id,
            score=float(d.relevance_score) if d.relevance_score else None,
            title="",  # Stub: Document join not implemented
        )
        for d in docs
    ]
    
    return GetMessageSourcesResponse(sources=sources)


@router.post("/messages/{message_id}/feedback", response_model=MessageFeedback)
async def submit_feedback(
    message_id: int,
    data: SubmitFeedbackRequest,
    user: CurrentUser,
    db: DbSession,
) -> MessageFeedback:
    """
    Submit feedback on a message.

    Args:
        message_id: The ID of the message.
        data: The feedback data.
        user: The authenticated user.
        db: Database session.

    Returns:
        MessageFeedback: The created or updated feedback.

    Raises:
        HTTPException: 404 if message not found.
    """
    # Verify message ownership
    msg_result = await db.execute(
        select(ChatMessageORM)
        .join(ChatSessionORM, ChatMessageORM.chat_session_id == ChatSessionORM.id)
        .where(ChatMessageORM.id == message_id)
        .where(ChatSessionORM.user_id == user.id)
        .where(ChatSessionORM.deleted_date.is_(None))
    )
    db_message = msg_result.scalar_one_or_none()
    
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Check for existing feedback
    existing_result = await db.execute(
        select(ChatMessageFeedbackORM)
        .where(ChatMessageFeedbackORM.chat_message_id == message_id)
        .where(ChatMessageFeedbackORM.user_id == user.id)
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        # Update existing feedback
        if data.is_positive is not None:
            existing.is_positive = data.is_positive
        existing.feedback_text = data.feedback_text
        existing.user_id_last_update = user.id
        return MessageFeedback.model_validate(existing, from_attributes=True)
    
    # Create new feedback
    feedback = ChatMessageFeedbackORM(
        chat_message_id=message_id,
        user_id=user.id,
        is_positive=data.is_positive,
        feedback_text=data.feedback_text,
        user_id_last_update=user.id,
    )
    
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)
    
    return MessageFeedback.model_validate(feedback, from_attributes=True)
