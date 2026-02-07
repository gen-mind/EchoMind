# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   common_model.py
@Time    :   2026-02-07 17:47:19
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class PaginationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    page: Optional[int] = _Field(default=0)
    limit: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.PaginationRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "PaginationRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class PaginationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    page: Optional[int] = _Field(default=0)
    limit: Optional[int] = _Field(default=0)
    total: Optional[int] = _Field(default=0)
    pages: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.PaginationResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "PaginationResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class FieldError(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    field: Optional[str] = _Field(default="")
    message: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.FieldError")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "FieldError":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    code: Optional[str] = _Field(default="")
    message: Optional[str] = _Field(default="")
    details: Optional[List[FieldError]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.ErrorResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ErrorResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class AuditInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)
    user_id_last_update: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.AuditInfo")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "AuditInfo":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class Empty(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.Empty")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Empty":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class IdRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.IdRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "IdRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class SuccessResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    success: Optional[bool] = _Field(default=False)
    message: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.common.SuccessResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "SuccessResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
