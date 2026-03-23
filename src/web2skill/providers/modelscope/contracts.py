from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Generic, TypeVar

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


class LoginBootstrapResult(BaseModel):
    trace_id: str
    storage_state_path: str
    authenticated: bool
    message: str


class DriftProbeKind(str, Enum):
    API = "api"
    DOM = "dom"


class DriftProbe(BaseModel):
    name: str
    kind: DriftProbeKind
    target: str
    expectation: str


ResultT = TypeVar("ResultT")


class SkillResult(BaseModel, Generic[ResultT]):
    trace_id: str
    capability: CapabilityName
    strategy_used: StrategyUsed
    requires_human: bool
    data: ResultT | None = None
    errors: list[str] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=_empty_trace)
