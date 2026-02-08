from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ConnectorType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONNECTOR_TYPE_UNSPECIFIED: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_TEAMS: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_GOOGLE_DRIVE: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_ONEDRIVE: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_WEB: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_FILE: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_GMAIL: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_GOOGLE_CALENDAR: _ClassVar[ConnectorType]
    CONNECTOR_TYPE_GOOGLE_CONTACTS: _ClassVar[ConnectorType]

class ConnectorStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONNECTOR_STATUS_UNSPECIFIED: _ClassVar[ConnectorStatus]
    CONNECTOR_STATUS_PENDING: _ClassVar[ConnectorStatus]
    CONNECTOR_STATUS_SYNCING: _ClassVar[ConnectorStatus]
    CONNECTOR_STATUS_ACTIVE: _ClassVar[ConnectorStatus]
    CONNECTOR_STATUS_ERROR: _ClassVar[ConnectorStatus]
    CONNECTOR_STATUS_DISABLED: _ClassVar[ConnectorStatus]

class ConnectorScope(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONNECTOR_SCOPE_UNSPECIFIED: _ClassVar[ConnectorScope]
    CONNECTOR_SCOPE_USER: _ClassVar[ConnectorScope]
    CONNECTOR_SCOPE_GROUP: _ClassVar[ConnectorScope]
    CONNECTOR_SCOPE_ORG: _ClassVar[ConnectorScope]
CONNECTOR_TYPE_UNSPECIFIED: ConnectorType
CONNECTOR_TYPE_TEAMS: ConnectorType
CONNECTOR_TYPE_GOOGLE_DRIVE: ConnectorType
CONNECTOR_TYPE_ONEDRIVE: ConnectorType
CONNECTOR_TYPE_WEB: ConnectorType
CONNECTOR_TYPE_FILE: ConnectorType
CONNECTOR_TYPE_GMAIL: ConnectorType
CONNECTOR_TYPE_GOOGLE_CALENDAR: ConnectorType
CONNECTOR_TYPE_GOOGLE_CONTACTS: ConnectorType
CONNECTOR_STATUS_UNSPECIFIED: ConnectorStatus
CONNECTOR_STATUS_PENDING: ConnectorStatus
CONNECTOR_STATUS_SYNCING: ConnectorStatus
CONNECTOR_STATUS_ACTIVE: ConnectorStatus
CONNECTOR_STATUS_ERROR: ConnectorStatus
CONNECTOR_STATUS_DISABLED: ConnectorStatus
CONNECTOR_SCOPE_UNSPECIFIED: ConnectorScope
CONNECTOR_SCOPE_USER: ConnectorScope
CONNECTOR_SCOPE_GROUP: ConnectorScope
CONNECTOR_SCOPE_ORG: ConnectorScope

class Connector(_message.Message):
    __slots__ = ("id", "name", "type", "config", "state", "refresh_freq_minutes", "user_id", "scope", "scope_id", "status", "status_message", "last_sync_at", "docs_analyzed", "creation_date", "last_update")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REFRESH_FREQ_MINUTES_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    LAST_SYNC_AT_FIELD_NUMBER: _ClassVar[int]
    DOCS_ANALYZED_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    type: ConnectorType
    config: _struct_pb2.Struct
    state: _struct_pb2.Struct
    refresh_freq_minutes: int
    user_id: int
    scope: ConnectorScope
    scope_id: str
    status: ConnectorStatus
    status_message: str
    last_sync_at: _timestamp_pb2.Timestamp
    docs_analyzed: int
    creation_date: _timestamp_pb2.Timestamp
    last_update: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., type: _Optional[_Union[ConnectorType, str]] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., state: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., refresh_freq_minutes: _Optional[int] = ..., user_id: _Optional[int] = ..., scope: _Optional[_Union[ConnectorScope, str]] = ..., scope_id: _Optional[str] = ..., status: _Optional[_Union[ConnectorStatus, str]] = ..., status_message: _Optional[str] = ..., last_sync_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., docs_analyzed: _Optional[int] = ..., creation_date: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_update: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateConnectorRequest(_message.Message):
    __slots__ = ("name", "type", "config", "refresh_freq_minutes", "scope", "scope_id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    REFRESH_FREQ_MINUTES_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: ConnectorType
    config: _struct_pb2.Struct
    refresh_freq_minutes: int
    scope: ConnectorScope
    scope_id: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[ConnectorType, str]] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., refresh_freq_minutes: _Optional[int] = ..., scope: _Optional[_Union[ConnectorScope, str]] = ..., scope_id: _Optional[str] = ...) -> None: ...

class UpdateConnectorRequest(_message.Message):
    __slots__ = ("id", "name", "config", "refresh_freq_minutes", "scope", "scope_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    REFRESH_FREQ_MINUTES_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    config: _struct_pb2.Struct
    refresh_freq_minutes: int
    scope: ConnectorScope
    scope_id: str
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., refresh_freq_minutes: _Optional[int] = ..., scope: _Optional[_Union[ConnectorScope, str]] = ..., scope_id: _Optional[str] = ...) -> None: ...

class ListConnectorsRequest(_message.Message):
    __slots__ = ("pagination", "type", "status")
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    pagination: _common_pb2.PaginationRequest
    type: ConnectorType
    status: ConnectorStatus
    def __init__(self, pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ..., type: _Optional[_Union[ConnectorType, str]] = ..., status: _Optional[_Union[ConnectorStatus, str]] = ...) -> None: ...

class ListConnectorsResponse(_message.Message):
    __slots__ = ("connectors", "pagination")
    CONNECTORS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    connectors: _containers.RepeatedCompositeFieldContainer[Connector]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, connectors: _Optional[_Iterable[_Union[Connector, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class GetConnectorResponse(_message.Message):
    __slots__ = ("connector",)
    CONNECTOR_FIELD_NUMBER: _ClassVar[int]
    connector: Connector
    def __init__(self, connector: _Optional[_Union[Connector, _Mapping]] = ...) -> None: ...

class TriggerSyncResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetConnectorStatusResponse(_message.Message):
    __slots__ = ("status", "status_message", "last_sync_at", "docs_analyzed", "docs_pending")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    LAST_SYNC_AT_FIELD_NUMBER: _ClassVar[int]
    DOCS_ANALYZED_FIELD_NUMBER: _ClassVar[int]
    DOCS_PENDING_FIELD_NUMBER: _ClassVar[int]
    status: ConnectorStatus
    status_message: str
    last_sync_at: _timestamp_pb2.Timestamp
    docs_analyzed: int
    docs_pending: int
    def __init__(self, status: _Optional[_Union[ConnectorStatus, str]] = ..., status_message: _Optional[str] = ..., last_sync_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., docs_analyzed: _Optional[int] = ..., docs_pending: _Optional[int] = ...) -> None: ...
