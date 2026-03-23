from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field


def _trace_timestamp() -> datetime:
    return datetime.now(UTC)


def _empty_trace() -> list[TraceEvent]:
    return []


class StrategyUsed(str, Enum):
    NETWORK = "network"
    DOM = "dom"
    GUIDED_UI = "guided_ui"


class CapabilityName(str, Enum):
    SEARCH_MODELS = "modelscope.search_models"
    GET_MODEL_OVERVIEW = "modelscope.get_model_overview"
    LIST_MODEL_FILES = "modelscope.list_model_files"
    GET_QUICKSTART = "modelscope.get_quickstart"
    GET_ACCOUNT_PROFILE = "modelscope.get_account_profile"
    LIST_TOKENS = "modelscope.list_tokens"
    GET_TOKEN = "modelscope.get_token"
    CREATE_TOKEN = "modelscope.create_token"


class TraceEvent(BaseModel):
    stage: str
    detail: str
    strategy: StrategyUsed
    timestamp: datetime = Field(default_factory=_trace_timestamp)


class SearchModelsInput(BaseModel):
    query: str = Field(min_length=1)
    task: str | None = None
    sort: str = "relevance"
    page: int = Field(default=1, ge=1)


class ModelSlugInput(BaseModel):
    model_slug: str = Field(min_length=3)


class GetAccountProfileInput(BaseModel):
    pass


class ListTokensInput(BaseModel):
    pass


class GetTokenInput(BaseModel):
    token_id: int = Field(gt=0)
    confirm_reveal: bool = False


class CreateTokenValidity(str, Enum):
    PERMANENT = "permanent"
    SHORT_TERM = "short_term"


class CreateTokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    validity: CreateTokenValidity = CreateTokenValidity.PERMANENT
    confirm_create: bool = False


class OrganizationSummary(BaseModel):
    name: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None


class ModelSearchItem(BaseModel):
    model_slug: str
    name: str
    chinese_name: str | None = None
    description: str | None = None
    task_names: list[str] = Field(default_factory=list)
    license: str | None = None
    libraries: list[str] = Field(default_factory=list)
    downloads: int | None = None
    stars: int | None = None
    updated_at: datetime | None = None
    organization: OrganizationSummary | None = None
    model_url: str


class SearchModelsOutput(BaseModel):
    query: str
    total_count: int | None = None
    page: int
    items: list[ModelSearchItem]


class ModelOverview(BaseModel):
    model_slug: str
    name: str
    chinese_name: str | None = None
    headline: str | None = None
    description: str | None = None
    downloads: int | None = None
    stars: int | None = None
    revision: str | None = None
    license: str | None = None
    tasks: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    libraries: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    base_models: list[str] = Field(default_factory=list)
    storage_size: int | None = None
    updated_at: datetime | None = None
    organization: OrganizationSummary | None = None
    readme_markdown: str | None = None
    model_url: str


class ModelFileEntry(BaseModel):
    path: str
    name: str
    file_type: str
    size: int | None = None
    revision: str | None = None
    sha256: str | None = None
    committed_at: datetime | None = None
    committer_name: str | None = None
    is_lfs: bool = False


class ListModelFilesOutput(BaseModel):
    model_slug: str
    revision: str | None = None
    files: list[ModelFileEntry]


class QuickstartSnippet(BaseModel):
    heading: str
    body_markdown: str
    code_blocks: list[str] = Field(default_factory=list)


class AccountProfile(BaseModel):
    user_id: str | None = None
    username: str | None = None
    nickname: str | None = None
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    organization_names: list[str] = Field(default_factory=list)
    raw_profile: dict[str, object] = Field(default_factory=dict)


class TokenSummary(BaseModel):
    token_id: int
    name: str
    expires_at: datetime | None = None
    created_at: datetime | None = None
    valid: bool


class ListTokensOutput(BaseModel):
    items: list[TokenSummary]
    total_count: int


class TokenDetail(BaseModel):
    token_id: int
    name: str
    token: str
    expires_at: datetime | None = None
    created_at: datetime | None = None
    valid: bool


class CreateTokenOutput(BaseModel):
    token_id: int
    name: str
    token: str
    expires_at: datetime | None = None
    created_at: datetime | None = None
    valid: bool


class LoginBootstrapResult(BaseModel):
    trace_id: str
    storage_state_path: str
    authenticated: bool
    message: str


class DoctorResult(BaseModel):
    ok: bool
    message: str
    storage_state_path: str | None = None


ResultT = TypeVar("ResultT")


class SkillResult(BaseModel, Generic[ResultT]):
    trace_id: str
    capability: str
    strategy_used: StrategyUsed
    requires_human: bool
    data: ResultT | None = None
    errors: list[str] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=_empty_trace)


class StdioRequest(BaseModel):
    action: str | None = None
    bundle_id: str | None = None
    provider: str | None = None
    capability_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    session_id: str | None = None
    session: dict[str, Any] | None = None
    storage_state_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionLoginInput(BaseModel):
    mode: Literal["interactive", "import_browser"] = "interactive"
    browser: str = "auto"
    storage_state_path: str | None = None
    entry_model_slug: str = "Qwen/Qwen2.5-7B-Instruct"
    timeout_seconds: int = Field(default=300, ge=1)
