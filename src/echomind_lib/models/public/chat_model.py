# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   chat_model.py
@Time    :   2026-02-08 14:39:02
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from ..common_model import PaginationRequest, PaginationResponse
from enum import Enum as _Enum
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type, Any


class ChatMode(_Enum):
    CHAT_MODE_UNSPECIFIED = 0
    CHAT_MODE_CHAT = 1
    CHAT_MODE_SEARCH = 2


class MessageRole(_Enum):
    MESSAGE_ROLE_UNSPECIFIED = 0
    MESSAGE_ROLE_USER = 1
    MESSAGE_ROLE_ASSISTANT = 2
    MESSAGE_ROLE_SYSTEM = 3


class ChatSession(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    assistant_id: Optional[int] = _Field(default=0)
    title: Optional[str] = _Field(default="")
    mode: Optional[ChatMode] = _Field(default=ChatMode(0))
    message_count: Optional[int] = _Field(default=0)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)
    last_message_at: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ChatSession")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ChatSession":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ChatMessage(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    chat_session_id: Optional[int] = _Field(default=0)
    role: Optional[MessageRole] = _Field(default=MessageRole(0))
    content: Optional[str] = _Field(default="")
    token_count: Optional[int] = _Field(default=0)
    parent_message_id: Optional[int] = _Field(default=0)
    rephrased_query: Optional[str] = _Field(default="")
    retrieval_context: Optional[dict[str, Any]] = _Field(default=None)
    tool_calls: Optional[dict[str, Any]] = _Field(default=None)
    error: Optional[str] = _Field(default="")
    creation_date: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ChatMessage")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ChatMessage":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class MessageSource(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    document_id: Optional[int] = _Field(default=0)
    chunk_id: Optional[str] = _Field(default="")
    score: Optional[float] = _Field(default=0.0)
    title: Optional[str] = _Field(default="")
    snippet: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.MessageSource")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "MessageSource":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class MessageFeedback(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    chat_message_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    is_positive: Optional[bool] = _Field(default=False)
    feedback_text: Optional[str] = _Field(default="")
    creation_date: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.MessageFeedback")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "MessageFeedback":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateChatSessionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    assistant_id: Optional[int] = _Field(default=0)
    title: Optional[str] = _Field(default="")
    mode: Optional[ChatMode] = _Field(default=ChatMode(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.CreateChatSessionRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateChatSessionRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListChatSessionsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    assistant_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListChatSessionsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListChatSessionsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListChatSessionsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    sessions: Optional[List[ChatSession]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListChatSessionsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListChatSessionsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetChatSessionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session: Optional[ChatSession] = _Field(default=None)
    messages: Optional[List[ChatMessage]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetChatSessionResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetChatSessionResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListMessagesRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    pagination: Optional[PaginationRequest] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListMessagesRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListMessagesRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListMessagesResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    messages: Optional[List[ChatMessage]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListMessagesResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListMessagesResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetMessageResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    message: Optional[ChatMessage] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetMessageResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetMessageResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetMessageSourcesResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    sources: Optional[List[MessageSource]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetMessageSourcesResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetMessageSourcesResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class SubmitFeedbackRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    message_id: Optional[int] = _Field(default=0)
    is_positive: Optional[bool] = _Field(default=False)
    feedback_text: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.SubmitFeedbackRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "SubmitFeedbackRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class SubmitFeedbackResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    feedback: Optional[MessageFeedback] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.SubmitFeedbackResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "SubmitFeedbackResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsChatStart(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    query: Optional[str] = _Field(default="")
    mode: Optional[ChatMode] = _Field(default=ChatMode(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsChatStart")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsChatStart":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsChatCancel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsChatCancel")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsChatCancel":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsRetrievalStart(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    query: Optional[str] = _Field(default="")
    rephrased_query: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsRetrievalStart")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsRetrievalStart":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsRetrievalComplete(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    sources: Optional[List[MessageSource]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsRetrievalComplete")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsRetrievalComplete":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsGenerationToken(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    token: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsGenerationToken")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsGenerationToken":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsGenerationComplete(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    message_id: Optional[int] = _Field(default=0)
    token_count: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsGenerationComplete")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsGenerationComplete":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class WsError(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    code: Optional[str] = _Field(default="")
    message: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.WsError")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "WsError":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
