from google.protobuf import timestamp_pb2 as _timestamp_pb2
import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LLMProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LLM_PROVIDER_UNSPECIFIED: _ClassVar[LLMProvider]
    LLM_PROVIDER_OPENAI_COMPATIBLE: _ClassVar[LLMProvider]
    LLM_PROVIDER_ANTHROPIC: _ClassVar[LLMProvider]
    LLM_PROVIDER_ANTHROPIC_TOKEN: _ClassVar[LLMProvider]
LLM_PROVIDER_UNSPECIFIED: LLMProvider
LLM_PROVIDER_OPENAI_COMPATIBLE: LLMProvider
LLM_PROVIDER_ANTHROPIC: LLMProvider
LLM_PROVIDER_ANTHROPIC_TOKEN: LLMProvider

class LLM(_message.Message):
    __slots__ = ("id", "name", "provider", "model_id", "endpoint", "has_api_key", "max_tokens", "temperature", "is_default", "is_active", "creation_date", "last_update")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    HAS_API_KEY_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    provider: LLMProvider
    model_id: str
    endpoint: str
    has_api_key: bool
    max_tokens: int
    temperature: float
    is_default: bool
    is_active: bool
    creation_date: _timestamp_pb2.Timestamp
    last_update: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., provider: _Optional[_Union[LLMProvider, str]] = ..., model_id: _Optional[str] = ..., endpoint: _Optional[str] = ..., has_api_key: bool = ..., max_tokens: _Optional[int] = ..., temperature: _Optional[float] = ..., is_default: bool = ..., is_active: bool = ..., creation_date: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_update: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateLLMRequest(_message.Message):
    __slots__ = ("name", "provider", "model_id", "endpoint", "api_key", "max_tokens", "temperature", "is_default", "is_active")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    API_KEY_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    name: str
    provider: LLMProvider
    model_id: str
    endpoint: str
    api_key: str
    max_tokens: int
    temperature: float
    is_default: bool
    is_active: bool
    def __init__(self, name: _Optional[str] = ..., provider: _Optional[_Union[LLMProvider, str]] = ..., model_id: _Optional[str] = ..., endpoint: _Optional[str] = ..., api_key: _Optional[str] = ..., max_tokens: _Optional[int] = ..., temperature: _Optional[float] = ..., is_default: bool = ..., is_active: bool = ...) -> None: ...

class UpdateLLMRequest(_message.Message):
    __slots__ = ("id", "name", "provider", "model_id", "endpoint", "api_key", "max_tokens", "temperature", "is_default", "is_active")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    API_KEY_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    provider: LLMProvider
    model_id: str
    endpoint: str
    api_key: str
    max_tokens: int
    temperature: float
    is_default: bool
    is_active: bool
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., provider: _Optional[_Union[LLMProvider, str]] = ..., model_id: _Optional[str] = ..., endpoint: _Optional[str] = ..., api_key: _Optional[str] = ..., max_tokens: _Optional[int] = ..., temperature: _Optional[float] = ..., is_default: bool = ..., is_active: bool = ...) -> None: ...

class ListLLMsRequest(_message.Message):
    __slots__ = ("pagination", "is_active")
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    pagination: _common_pb2.PaginationRequest
    is_active: bool
    def __init__(self, pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ..., is_active: bool = ...) -> None: ...

class ListLLMsResponse(_message.Message):
    __slots__ = ("llms", "pagination")
    LLMS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    llms: _containers.RepeatedCompositeFieldContainer[LLM]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, llms: _Optional[_Iterable[_Union[LLM, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class GetLLMResponse(_message.Message):
    __slots__ = ("llm",)
    LLM_FIELD_NUMBER: _ClassVar[int]
    llm: LLM
    def __init__(self, llm: _Optional[_Union[LLM, _Mapping]] = ...) -> None: ...

class TestLLMResponse(_message.Message):
    __slots__ = ("success", "message", "latency_ms")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    latency_ms: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., latency_ms: _Optional[int] = ...) -> None: ...
