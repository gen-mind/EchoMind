from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ProjectorGenerateRequest(_message.Message):
    __slots__ = ("viz_id", "collection_name", "search_query", "limit", "team_id", "org_id")
    VIZ_ID_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    SEARCH_QUERY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    ORG_ID_FIELD_NUMBER: _ClassVar[int]
    viz_id: str
    collection_name: str
    search_query: str
    limit: int
    team_id: int
    org_id: int
    def __init__(self, viz_id: _Optional[str] = ..., collection_name: _Optional[str] = ..., search_query: _Optional[str] = ..., limit: _Optional[int] = ..., team_id: _Optional[int] = ..., org_id: _Optional[int] = ...) -> None: ...
