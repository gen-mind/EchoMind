# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   assistant_model.py
@Time    :   2026-01-26 15:41:22
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from .common_model import PaginationRequest, PaginationResponse
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class Assistant(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    llm_id: Optional[int] = _Field(default=0)
    system_prompt: Optional[str] = _Field(default="")
    task_prompt: Optional[str] = _Field(default="")
    starter_messages: Optional[List[str]] = _Field(default="")
    is_default: Optional[bool] = _Field(default=False)
    is_visible: Optional[bool] = _Field(default=False)
    display_priority: Optional[int] = _Field(default=0)
    created_by: Optional[int] = _Field(default=0)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.Assistant")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Assistant":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateAssistantRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    llm_id: Optional[int] = _Field(default=0)
    system_prompt: Optional[str] = _Field(default="")
    task_prompt: Optional[str] = _Field(default="")
    starter_messages: Optional[List[str]] = _Field(default="")
    is_default: Optional[bool] = _Field(default=False)
    is_visible: Optional[bool] = _Field(default=False)
    display_priority: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.CreateAssistantRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateAssistantRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateAssistantRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    llm_id: Optional[int] = _Field(default=0)
    system_prompt: Optional[str] = _Field(default="")
    task_prompt: Optional[str] = _Field(default="")
    starter_messages: Optional[List[str]] = _Field(default="")
    is_default: Optional[bool] = _Field(default=False)
    is_visible: Optional[bool] = _Field(default=False)
    display_priority: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UpdateAssistantRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateAssistantRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListAssistantsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    is_visible: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListAssistantsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListAssistantsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListAssistantsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    assistants: Optional[List[Assistant]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListAssistantsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListAssistantsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetAssistantResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    assistant: Optional[Assistant] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetAssistantResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetAssistantResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
