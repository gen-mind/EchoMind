# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   embedding_model.py
@Time    :   2026-02-03 01:32:40
@Desc    :   Generated Pydantic models from protobuf definitions
"""

from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class EmbedRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    texts: Optional[List[str]] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.EmbedRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "EmbedRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class Embedding(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    vector: Optional[List[float]] = _Field(default=0.0)
    dimension: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.Embedding")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Embedding":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class EmbedResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    embeddings: Optional[List[Embedding]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.EmbedResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "EmbedResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class DimensionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.DimensionRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "DimensionRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class DimensionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dimension: Optional[int] = _Field(default=0)
    model_id: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.DimensionResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "DimensionResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
