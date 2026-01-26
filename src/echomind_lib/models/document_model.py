# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   document_model.py
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


class DocumentStatus(_Enum):
    DOCUMENT_STATUS_UNSPECIFIED = 0
    DOCUMENT_STATUS_PENDING = 1
    DOCUMENT_STATUS_PROCESSING = 2
    DOCUMENT_STATUS_COMPLETED = 3
    DOCUMENT_STATUS_FAILED = 4


class Document(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    parent_id: Optional[int] = _Field(default=0)
    connector_id: Optional[int] = _Field(default=0)
    source_id: Optional[str] = _Field(default="")
    url: Optional[str] = _Field(default="")
    original_url: Optional[str] = _Field(default="")
    title: Optional[str] = _Field(default="")
    content_type: Optional[str] = _Field(default="")
    status: Optional[DocumentStatus] = _Field(default=DocumentStatus(0))
    status_message: Optional[str] = _Field(default="")
    chunk_count: Optional[int] = _Field(default=0)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.Document")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Document":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListDocumentsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    connector_id: Optional[int] = _Field(default=0)
    status: Optional[DocumentStatus] = _Field(default=DocumentStatus(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListDocumentsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListDocumentsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListDocumentsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    documents: Optional[List[Document]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListDocumentsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListDocumentsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetDocumentResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    document: Optional[Document] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetDocumentResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetDocumentResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class SearchDocumentsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    query: Optional[str] = _Field(default="")
    connector_id: Optional[int] = _Field(default=0)
    limit: Optional[int] = _Field(default=0)
    min_score: Optional[float] = _Field(default=0.0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.SearchDocumentsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "SearchDocumentsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class DocumentSearchResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    document: Optional[Document] = _Field(default=None)
    chunk_id: Optional[str] = _Field(default="")
    chunk_content: Optional[str] = _Field(default="")
    score: Optional[float] = _Field(default=0.0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.DocumentSearchResult")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "DocumentSearchResult":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class SearchDocumentsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    results: Optional[List[DocumentSearchResult]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.SearchDocumentsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "SearchDocumentsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
