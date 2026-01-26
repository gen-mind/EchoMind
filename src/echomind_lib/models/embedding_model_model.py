# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   embedding_model_model.py
@Time    :   2026-01-26 15:41:22
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class EmbeddingModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    model_id: Optional[str] = _Field(default="")
    model_name: Optional[str] = _Field(default="")
    model_dimension: Optional[int] = _Field(default=0)
    endpoint: Optional[str] = _Field(default="")
    is_active: Optional[bool] = _Field(default=False)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.EmbeddingModel")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "EmbeddingModel":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateEmbeddingModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: Optional[str] = _Field(default="")
    model_name: Optional[str] = _Field(default="")
    model_dimension: Optional[int] = _Field(default=0)
    endpoint: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.CreateEmbeddingModelRequest"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateEmbeddingModelRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListEmbeddingModelsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    models: Optional[List[EmbeddingModel]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.ListEmbeddingModelsResponse"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListEmbeddingModelsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetActiveEmbeddingModelResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model: Optional[EmbeddingModel] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.GetActiveEmbeddingModelResponse"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetActiveEmbeddingModelResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ActivateEmbeddingModelResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    success: Optional[bool] = _Field(default=False)
    message: Optional[str] = _Field(default="")
    requires_reindex: Optional[bool] = _Field(default=False)
    documents_affected: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.ActivateEmbeddingModelResponse"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ActivateEmbeddingModelResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
