from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import Field

from web2skill.core.contracts import MetadataValue, RuntimeBaseModel, SessionId


def default_session_root() -> Path:
    return Path.home() / ".web2skill" / "sessions"


class SessionRecord(RuntimeBaseModel):
    session_id: SessionId
    provider_name: str = Field(min_length=1, max_length=64)
    storage_state_path: Path | None = None
    base_url: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        provider_name: str,
        storage_state_path: Path | None = None,
        base_url: str | None = None,
        metadata: dict[str, MetadataValue] | None = None,
        expires_at: datetime | None = None,
    ) -> SessionRecord:
        now = datetime.now(UTC)
        return cls(
            session_id=session_id,
            provider_name=provider_name,
            storage_state_path=storage_state_path,
            base_url=base_url,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

    def touch(self) -> SessionRecord:
        return self.model_copy(update={"updated_at": datetime.now(UTC)})


class SessionStore(Protocol):
    def get(self, session_id: str) -> SessionRecord | None: ...

    def put(self, session: SessionRecord) -> SessionRecord: ...

    def delete(self, session_id: str) -> None: ...

    def list(self, provider_name: str | None = None) -> list[SessionRecord]: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def put(self, session: SessionRecord) -> SessionRecord:
        stored = session.touch()
        self._sessions[stored.session_id] = stored
        return stored

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list(self, provider_name: str | None = None) -> list[SessionRecord]:
        sessions = list(self._sessions.values())
        if provider_name is None:
            return sorted(sessions, key=lambda item: item.updated_at, reverse=True)
        return sorted(
            (item for item in sessions if item.provider_name == provider_name),
            key=lambda item: item.updated_at,
            reverse=True,
        )


class FileSessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_session_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, session_id: str) -> SessionRecord | None:
        path = self.root / f"{session_id}.json"
        if not path.exists():
            return None
        return SessionRecord.model_validate_json(path.read_text())

    def put(self, session: SessionRecord) -> SessionRecord:
        stored = session.touch()
        path = self.root / f"{stored.session_id}.json"
        path.write_text(stored.model_dump_json(indent=2))
        return stored

    def delete(self, session_id: str) -> None:
        path = self.root / f"{session_id}.json"
        path.unlink(missing_ok=True)

    def list(self, provider_name: str | None = None) -> list[SessionRecord]:
        sessions: list[SessionRecord] = []
        for path in sorted(self.root.glob("*.json")):
            session = SessionRecord.model_validate_json(path.read_text())
            if provider_name is None or session.provider_name == provider_name:
                sessions.append(session)
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)


def export_storage_state(session: SessionRecord) -> str:
    payload = session.model_dump(mode="json")
    return json.dumps(payload, indent=2)
