# !/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   orchestrator_model.py
@Time    :   2026-02-03 01:32:40
@Desc    :   Generated Pydantic models from protobuf definitions
'''
from ..public.connector_model import ConnectorScope, ConnectorType
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import Optional, Type, Any


class ConnectorSyncRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    connector_id: Optional[int] = _Field(default=0)
    type: Optional[ConnectorType] = _Field(default=ConnectorType(0))
    user_id: Optional[int] = _Field(default=0)
    scope: Optional[ConnectorScope] = _Field(default=ConnectorScope(0))
    scope_id: Optional[str] = _Field(default="")
    config: Optional[dict[str, Any]] = _Field(default=None)
    state: Optional[dict[str, Any]] = _Field(default=None)
    chunking_session: Optional[str] = _Field(default="")

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.ConnectorSyncRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> 'ConnectorSyncRequest':
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)

class DocumentProcessRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    document_id: Optional[int] = _Field(default=0)
    connector_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    minio_path: Optional[str] = _Field(default="")
    chunking_session: Optional[str] = _Field(default="")
    scope: Optional[ConnectorScope] = _Field(default=ConnectorScope(0))
    scope_id: Optional[str] = _Field(default="")
    team_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.internal.DocumentProcessRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> 'DocumentProcessRequest':
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)

