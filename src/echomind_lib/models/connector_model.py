# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   connector_model.py
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


class ConnectorType(_Enum):
    CONNECTOR_TYPE_UNSPECIFIED = 0
    CONNECTOR_TYPE_TEAMS = 1
    CONNECTOR_TYPE_GOOGLE_DRIVE = 2
    CONNECTOR_TYPE_ONEDRIVE = 3
    CONNECTOR_TYPE_WEB = 4
    CONNECTOR_TYPE_FILE = 5


class ConnectorStatus(_Enum):
    CONNECTOR_STATUS_UNSPECIFIED = 0
    CONNECTOR_STATUS_PENDING = 1
    CONNECTOR_STATUS_SYNCING = 2
    CONNECTOR_STATUS_ACTIVE = 3
    CONNECTOR_STATUS_ERROR = 4
    CONNECTOR_STATUS_DISABLED = 5


class ConnectorScope(_Enum):
    CONNECTOR_SCOPE_UNSPECIFIED = 0
    CONNECTOR_SCOPE_USER = 1
    CONNECTOR_SCOPE_GROUP = 2
    CONNECTOR_SCOPE_ORG = 3


class Connector(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    type: Optional[ConnectorType] = _Field(default=ConnectorType(0))
    config: Optional[Struct] = _Field(default=None)
    state: Optional[Struct] = _Field(default=None)
    refresh_freq_minutes: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    scope: Optional[ConnectorScope] = _Field(default=ConnectorScope(0))
    scope_id: Optional[str] = _Field(default="")
    status: Optional[ConnectorStatus] = _Field(default=ConnectorStatus(0))
    status_message: Optional[str] = _Field(default="")
    last_sync_at: Optional[datetime.datetime] = _Field(default=None)
    docs_analyzed: Optional[int] = _Field(default=0)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.Connector")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Connector":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateConnectorRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: Optional[str] = _Field(default="")
    type: Optional[ConnectorType] = _Field(default=ConnectorType(0))
    config: Optional[Struct] = _Field(default=None)
    refresh_freq_minutes: Optional[int] = _Field(default=0)
    scope: Optional[ConnectorScope] = _Field(default=ConnectorScope(0))
    scope_id: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.CreateConnectorRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateConnectorRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateConnectorRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    config: Optional[Struct] = _Field(default=None)
    refresh_freq_minutes: Optional[int] = _Field(default=0)
    scope: Optional[ConnectorScope] = _Field(default=ConnectorScope(0))
    scope_id: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UpdateConnectorRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateConnectorRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListConnectorsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    type: Optional[ConnectorType] = _Field(default=ConnectorType(0))
    status: Optional[ConnectorStatus] = _Field(default=ConnectorStatus(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListConnectorsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListConnectorsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListConnectorsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    connectors: Optional[List[Connector]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListConnectorsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListConnectorsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetConnectorResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    connector: Optional[Connector] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetConnectorResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetConnectorResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class TriggerSyncResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    success: Optional[bool] = _Field(default=False)
    message: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.TriggerSyncResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "TriggerSyncResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetConnectorStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    status: Optional[ConnectorStatus] = _Field(default=ConnectorStatus(0))
    status_message: Optional[str] = _Field(default="")
    last_sync_at: Optional[datetime.datetime] = _Field(default=None)
    docs_analyzed: Optional[int] = _Field(default=0)
    docs_pending: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.GetConnectorStatusResponse"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetConnectorStatusResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
