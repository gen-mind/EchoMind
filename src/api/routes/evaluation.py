"""
RAGAS batch evaluation endpoint.

Admin-only endpoint for triggering batch RAG quality evaluation
across recent chat sessions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.dependencies import AdminUser, DbSession
from api.logic.ragas_evaluator import maybe_evaluate_async
from echomind_lib.db.models import (
    ChatMessage as ChatMessageORM,
    ChatMessageDocument as ChatMessageDocumentORM,
    ChatSession as ChatSessionORM,
    Document as DocumentORM,
)
from echomind_lib.helpers.langfuse_helper import create_trace, is_langfuse_enabled

logger = logging.getLogger(__name__)

router = APIRouter()


class BatchEvalRequest(BaseModel):
    """Request for batch evaluation.

    Attributes:
        limit: Maximum number of sessions to evaluate.
        min_messages: Minimum messages in session to be eligible.
    """

    limit: int = Field(default=50, ge=1, le=500, description="Max sessions to evaluate")
    min_messages: int = Field(default=2, ge=2, description="Min messages in session")


class BatchEvalResponse(BaseModel):
    """Response from batch evaluation.

    Attributes:
        evaluated: Number of sessions evaluated.
        skipped: Number of sessions skipped.
        errors: Number of evaluation errors.
    """

    evaluated: int = 0
    skipped: int = 0
    errors: int = 0


@router.post(
    "/batch",
    response_model=BatchEvalResponse,
    summary="Run batch RAGAS evaluation",
    description="Evaluate recent chat sessions with RAGAS metrics. Admin only.",
)
async def run_batch_evaluation(
    request: BatchEvalRequest,
    user: AdminUser,
    db: DbSession,
) -> BatchEvalResponse:
    """
    Run batch RAGAS evaluation on recent chat sessions.

    Fetches recent sessions with sufficient messages, extracts
    query/response/context triples, and evaluates each with RAGAS.

    Args:
        request: Batch evaluation parameters.
        user: Authenticated user (must be admin).
        db: Database session.

    Returns:
        Summary of evaluation results.
    """
    if not is_langfuse_enabled():
        logger.warning("⚠️ Batch eval requested but Langfuse is disabled")
        return BatchEvalResponse(skipped=request.limit)

    # Fetch recent sessions with messages
    result = await db.execute(
        select(ChatSessionORM)
        .where(ChatSessionORM.deleted_date.is_(None))
        .where(ChatSessionORM.message_count >= request.min_messages)
        .order_by(ChatSessionORM.last_message_at.desc())
        .limit(request.limit)
    )
    sessions = result.scalars().all()

    response = BatchEvalResponse()

    for session in sessions:
        try:
            # Get last user message and assistant response
            messages_result = await db.execute(
                select(ChatMessageORM)
                .where(ChatMessageORM.chat_session_id == session.id)
                .order_by(ChatMessageORM.creation_date.desc())
                .limit(4)
            )
            messages = list(messages_result.scalars().all())
            messages.reverse()  # Chronological order

            # Find last user-assistant pair
            user_msg = None
            assistant_msg = None
            for msg in messages:
                if msg.role == "user":
                    user_msg = msg
                elif msg.role == "assistant" and user_msg is not None:
                    assistant_msg = msg
                    break

            if not user_msg or not assistant_msg:
                response.skipped += 1
                continue

            # Get context from linked documents
            doc_links_result = await db.execute(
                select(ChatMessageDocumentORM)
                .where(ChatMessageDocumentORM.chat_message_id == assistant_msg.id)
            )
            doc_links = doc_links_result.scalars().all()

            contexts: list[str] = []
            for link in doc_links:
                doc_result = await db.execute(
                    select(DocumentORM).where(DocumentORM.id == link.document_id)
                )
                doc = doc_result.scalar_one_or_none()
                if doc and doc.title:
                    contexts.append(doc.title)

            # Create trace for batch eval
            trace = create_trace(
                name="batch-evaluation",
                user_id=str(session.user_id),
                session_id=str(session.id),
                tags=["batch-eval"],
            )

            # Run evaluation (force 100% sample rate for batch)
            eval_result = await maybe_evaluate_async(
                trace_id=trace.id,
                query=user_msg.content,
                response=assistant_msg.content,
                contexts=contexts,
            )

            if eval_result:
                response.evaluated += 1
            else:
                response.skipped += 1

        except Exception as e:
            logger.warning(f"⚠️ Batch eval failed for session {session.id}: {e}")
            response.errors += 1

    logger.info(
        f"📊 Batch eval complete: {response.evaluated} evaluated, {response.skipped} skipped, {response.errors} errors"
    )

    return response
