# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   llm_model.py
@Time    :   2026-01-26 15:41:22
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from .common_model import PaginationRequest, PaginationResponse
from enum import Enum as _Enum
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class LLMProvider(_Enum):
    LLM_PROVIDER_UNSPECIFIED = 0
    LLM_PROVIDER_TGI = 1
    LLM_PROVIDER_VLLM = 2
    LLM_PROVIDER_OPENAI = 3
    LLM_PROVIDER_ANTHROPIC = 4
    LLM_PROVIDER_OLLAMA = 5


class LLM(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    provider: Optional[LLMProvider] = _Field(default=LLMProvider(0))
    model_id: Optional[str] = _Field(default="")
    endpoint: Optional[str] = _Field(default="")
    has_api_key: Optional[bool] = _Field(default=False)
    max_tokens: Optional[int] = _Field(default=0)
    temperature: Optional[float] = _Field(default=0.0)
    is_default: Optional[bool] = _Field(default=False)
    is_active: Optional[bool] = _Field(default=False)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.LLM")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "LLM":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateLLMRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: Optional[str] = _Field(default="")
    provider: Optional[LLMProvider] = _Field(default=LLMProvider(0))
    model_id: Optional[str] = _Field(default="")
    endpoint: Optional[str] = _Field(default="")
    api_key: Optional[str] = _Field(default="")
    max_tokens: Optional[int] = _Field(default=0)
    temperature: Optional[float] = _Field(default=0.0)
    is_default: Optional[bool] = _Field(default=False)
    is_active: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.CreateLLMRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateLLMRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateLLMRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    provider: Optional[LLMProvider] = _Field(default=LLMProvider(0))
    model_id: Optional[str] = _Field(default="")
    endpoint: Optional[str] = _Field(default="")
    api_key: Optional[str] = _Field(default="")
    max_tokens: Optional[int] = _Field(default=0)
    temperature: Optional[float] = _Field(default=0.0)
    is_default: Optional[bool] = _Field(default=False)
    is_active: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UpdateLLMRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateLLMRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListLLMsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    is_active: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListLLMsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListLLMsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListLLMsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    llms: Optional[List[LLM]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListLLMsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListLLMsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetLLMResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    llm: Optional[LLM] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetLLMResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetLLMResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class TestLLMResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    success: Optional[bool] = _Field(default=False)
    message: Optional[str] = _Field(default="")
    latency_ms: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.TestLLMResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "TestLLMResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
