# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   user_model.py
@Time    :   2026-01-26 15:41:22
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from .common_model import PaginationRequest, PaginationResponse
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import Dict, List, Optional, Type


class User(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    user_name: Optional[str] = _Field(default="")
    email: Optional[str] = _Field(default="")
    first_name: Optional[str] = _Field(default="")
    last_name: Optional[str] = _Field(default="")
    roles: Optional[List[str]] = _Field(default="")
    groups: Optional[List[str]] = _Field(default="")
    preferences: Optional[UserPreferences] = _Field(default=None)
    is_active: Optional[bool] = _Field(default=False)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)
    last_login: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.User")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "User":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UserPreferences(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    default_assistant_id: Optional[int] = _Field(default=0)
    theme: Optional[str] = _Field(default="")
    custom: Optional[Dict[str, str]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UserPreferences")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UserPreferences":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    first_name: Optional[str] = _Field(default="")
    last_name: Optional[str] = _Field(default="")
    preferences: Optional[UserPreferences] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UpdateUserRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateUserRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetCurrentUserResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    user: Optional[User] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetCurrentUserResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetCurrentUserResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListUsersRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    is_active: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListUsersRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListUsersRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListUsersResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    users: Optional[List[User]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListUsersResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListUsersResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
