# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   projector_model.py
@Time    :   2026-02-08 14:39:02
@Desc    :   Generated Pydantic models from protobuf definitions
"""

from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import Optional, Type


class ProjectorGenerateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    viz_id: Optional[str] = _Field(default="")
    collection_name: Optional[str] = _Field(default="")
    search_query: Optional[str] = _Field(default="")
    limit: Optional[int] = _Field(default=0)
    team_id: Optional[int] = _Field(default=0)
    org_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.internal.ProjectorGenerateRequest"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ProjectorGenerateRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
