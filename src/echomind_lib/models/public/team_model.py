# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   team_model.py
@Time    :   2026-02-07 17:47:19
@Desc    :   Generated Pydantic models from protobuf definitions
"""

import datetime
from ..common_model import PaginationRequest, PaginationResponse
from enum import Enum as _Enum
from google.protobuf import message as _message, message_factory
from protobuf_pydantic_gen.ext import model2protobuf, pool, protobuf2model
from pydantic import BaseModel, ConfigDict, Field as _Field
from typing import List, Optional, Type


class TeamMemberRole(_Enum):
    TEAM_MEMBER_ROLE_UNSPECIFIED = 0
    TEAM_MEMBER_ROLE_MEMBER = 1
    TEAM_MEMBER_ROLE_LEAD = 2


class Team(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    leader_id: Optional[int] = _Field(default=0)
    created_by: Optional[int] = _Field(default=0)
    member_count: Optional[int] = _Field(default=0)
    creation_date: Optional[datetime.datetime] = _Field(default=None)
    last_update: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.Team")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "Team":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class TeamMember(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    team_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    role: Optional[TeamMemberRole] = _Field(default=TeamMemberRole(0))
    added_at: Optional[datetime.datetime] = _Field(default=None)
    added_by: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.TeamMember")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "TeamMember":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class TeamMemberWithUser(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    user_id: Optional[int] = _Field(default=0)
    user_name: Optional[str] = _Field(default="")
    email: Optional[str] = _Field(default="")
    first_name: Optional[str] = _Field(default="")
    last_name: Optional[str] = _Field(default="")
    role: Optional[TeamMemberRole] = _Field(default=TeamMemberRole(0))
    added_at: Optional[datetime.datetime] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.TeamMemberWithUser")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "TeamMemberWithUser":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class CreateTeamRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    leader_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.CreateTeamRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "CreateTeamRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateTeamRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: Optional[int] = _Field(default=0)
    name: Optional[str] = _Field(default="")
    description: Optional[str] = _Field(default="")
    leader_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.UpdateTeamRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateTeamRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListTeamsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)
    include_member_count: Optional[bool] = _Field(default=False)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListTeamsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListTeamsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListTeamsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    teams: Optional[List[Team]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListTeamsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListTeamsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class GetTeamResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    team: Optional[Team] = _Field(default=None)
    members: Optional[List[TeamMemberWithUser]] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.GetTeamResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "GetTeamResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class AddTeamMemberRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    team_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    role: Optional[TeamMemberRole] = _Field(default=TeamMemberRole(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.AddTeamMemberRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "AddTeamMemberRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class RemoveTeamMemberRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    team_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.RemoveTeamMemberRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "RemoveTeamMemberRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class UpdateTeamMemberRoleRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    team_id: Optional[int] = _Field(default=0)
    user_id: Optional[int] = _Field(default=0)
    role: Optional[TeamMemberRole] = _Field(default=TeamMemberRole(0))

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName(
            "echomind.public.UpdateTeamMemberRoleRequest"
        )
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "UpdateTeamMemberRoleRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListUserTeamsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    pagination: Optional[PaginationRequest] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListUserTeamsRequest")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListUserTeamsRequest":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)


class ListUserTeamsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    teams: Optional[List[Team]] = _Field(default=None)
    pagination: Optional[PaginationResponse] = _Field(default=None)

    def to_protobuf(self) -> _message.Message:
        """Convert Pydantic model to protobuf message"""
        _proto = pool.FindMessageTypeByName("echomind.public.ListUserTeamsResponse")
        _cls: Type[_message.Message] = message_factory.GetMessageClass(_proto)
        return model2protobuf(self, _cls())

    @classmethod
    def from_protobuf(cls, src: _message.Message) -> "ListUserTeamsResponse":
        """Convert protobuf message to Pydantic model"""
        return protobuf2model(cls, src)
