from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# pyright: reportUnknownVariableType=false

StrategyName = Literal["network", "dom", "guided_ui"]
AuthMode = Literal["none", "session", "token"]
RiskLevel = Literal["low", "medium", "high"]
RuntimeKind = Literal["python_scripts"]
RuntimeEnv = Literal["core", "bundle"]


class RuntimeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RuntimeKind = "python_scripts"
    env: RuntimeEnv = "core"


class SessionHooks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_script: str | None = None
    doctor_script: str | None = None


class SkillExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input: dict[str, Any] | None = None
    output: Any = None


class AuthSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AuthMode
    login_required: bool = False
    session_provider: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_session_provider(self) -> AuthSpec:
        if self.mode == "session" and not self.session_provider:
            msg = "session_provider is required when auth mode is 'session'"
            raise ValueError(msg)
        return self


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    summary: str = Field(default="", min_length=0)
    description: str = Field(default="", min_length=0)
    risk: RiskLevel = "low"
    strategies: list[StrategyName] = Field(default_factory=lambda: ["network"])
    requires_confirmation: bool = False
    entry_script: str | None = None
    confirmation_field: str | None = None
    session_required: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    recovery: list[str] = Field(default_factory=list)
    human_handoff: list[str] = Field(default_factory=list)
    examples: list[SkillExample] = Field(default_factory=list)

    @field_validator("strategies", mode="before")
    @classmethod
    def normalize_strategies(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return ["guided_ui" if item == "ui" else item for item in value]

    @model_validator(mode="after")
    def validate_strategies(self) -> CapabilityManifest:
        if not self.summary:
            self.summary = self.name
        if not self.description:
            self.description = self.summary
        if not self.strategies:
            self.strategies = ["network"]
        if self.confirmation_field and not self.requires_confirmation:
            self.requires_confirmation = True
        return self


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", min_length=1)
    bundle_id: str = Field(default="", min_length=0)
    bundle_version: str = Field(default="1.0.0", min_length=1)
    provider: str = Field(min_length=1)
    provider_display_name: str = Field(default="", min_length=0)
    summary: str = Field(default="", min_length=0)
    description: str = Field(default="", min_length=0)
    base_url: AnyHttpUrl | None = None
    auth: AuthSpec = Field(default_factory=lambda: AuthSpec(mode="none"))
    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)
    session_hooks: SessionHooks = Field(default_factory=SessionHooks)
    prerequisites: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    recovery: list[str] = Field(default_factory=list)
    human_handoff: list[str] = Field(default_factory=list)
    capabilities: list[CapabilityManifest] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_capabilities(self) -> SkillManifest:
        if not self.bundle_id:
            self.bundle_id = self.provider
        if not self.provider_display_name:
            self.provider_display_name = self.provider
        if not self.summary:
            self.summary = self.provider_display_name
        if not self.description:
            self.description = self.summary
        names = [capability.name for capability in self.capabilities]
        if len(names) != len(set(names)):
            msg = f"duplicate capability names found in provider '{self.provider}'"
            raise ValueError(msg)
        for capability in self.capabilities:
            if not capability.name.startswith(f"{self.provider}."):
                msg = (
                    f"capability '{capability.name}' must start with "
                    f"provider prefix '{self.provider}.'"
                )
                raise ValueError(msg)
        if not self.capabilities:
            msg = f"provider '{self.provider}' must declare at least one capability"
            raise ValueError(msg)
        return self


class CapabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    name: str
    summary: str
    risk: RiskLevel
    strategies: list[StrategyName]
    auth_mode: AuthMode
    requires_confirmation: bool


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_display_name: str
    summary: str
    auth_mode: AuthMode
    capability_count: int
