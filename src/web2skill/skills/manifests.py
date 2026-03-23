from __future__ import annotations

from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

# pyright: reportUnknownVariableType=false

StrategyName = Literal["network", "dom", "ui"]
AuthMode = Literal["none", "session", "token"]
RiskLevel = Literal["low", "medium", "high"]


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
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk: RiskLevel = "low"
    strategies: list[StrategyName] = Field(default_factory=list)
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    recovery: list[str] = Field(default_factory=list)
    human_handoff: list[str] = Field(default_factory=list)
    examples: list[SkillExample] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strategies(self) -> CapabilityManifest:
        if not self.strategies:
            msg = f"capability '{self.name}' must declare at least one strategy"
            raise ValueError(msg)
        return self


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", min_length=1)
    provider: str = Field(min_length=1)
    provider_display_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    base_url: AnyHttpUrl | None = None
    auth: AuthSpec
    prerequisites: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    recovery: list[str] = Field(default_factory=list)
    human_handoff: list[str] = Field(default_factory=list)
    capabilities: list[CapabilityManifest] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_capabilities(self) -> SkillManifest:
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
