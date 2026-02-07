# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   agent_model.py
@Time    :   2026-02-07 17:47:19
@Desc    :   Generated Pydantic models from protobuf definitions
"""

from enum import Enum as _Enum
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type, Any


class MemoryType(_Enum):
    MEMORY_TYPE_UNSPECIFIED = 0
    MEMORY_TYPE_EPISODIC = 1
    MEMORY_TYPE_SEMANTIC = 2
    MEMORY_TYPE_PROCEDURAL = 3


class AgentMemory(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    memory_type: Optional[MemoryType] = _Field(default=MemoryType(0))
    content: Optional[str] = _Field(default="")
    embedding_id: Optional[str] = _Field(default="")
    importance_score: Optional[float] = _Field(default=0.0)
    access_count: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.AgentMemory")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "AgentMemory":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ToolCall(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    tool_name: Optional[str] = _Field(default="")
    parameters: Optional[dict[str, Any]] = _Field(default=None)
    result: Optional[dict[str, Any]] = _Field(default=None)
    duration_ms: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.ToolCall")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ToolCall":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class PlanStep(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    action: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    completed: Optional[bool] = _Field(default=False)
    result: Optional[dict[str, Any]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.PlanStep")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "PlanStep":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class AgentRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    query: Optional[str] = _Field(default="")
    relevant_memories: Optional[List[AgentMemory]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.AgentRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "AgentRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class AgentResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    response: Optional[str] = _Field(default="")
    tool_calls: Optional[List[ToolCall]] = _Field(default=None)
    plan: Optional[List[PlanStep]] = _Field(default=None)
    tokens_used: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.AgentResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "AgentResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
