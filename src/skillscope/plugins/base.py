"""Harness plugin protocol and discovery context.

No Cursor-specific types, paths, or JSON field names may appear here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from skillscope.domain.models import (
    ConversationSnapshot,
    IngestEligibility,
)


@dataclass(frozen=True)
class Platform:
    os: str  # "darwin", "linux", "win32"
    harness: str  # "cursor", etc.


@dataclass(frozen=True)
class DiscoveryContext:
    """Runtime configuration supplied by core to the plugin."""

    home: Path
    user_data: Path
    transcript_override: Path | None = None
    spool_override: Path | None = None
    contract_version: int = 1
    grace_seconds: int = 300


@dataclass(frozen=True)
class ConversationRef:
    """Opaque plugin-owned reference to a native conversation."""

    harness_id: str
    native_conversation_id: str
    source_locators: tuple[Path, ...] = ()
    extra: dict = field(default_factory=dict)


@runtime_checkable
class HarnessPlugin(Protocol):
    @property
    def id(self) -> str: ...

    def detect_platform(self) -> Platform: ...

    def discover(self, context: DiscoveryContext) -> Iterable[ConversationRef]: ...

    def inspect(
        self,
        conversation: ConversationRef,
        *,
        now: datetime,
        context: DiscoveryContext,
    ) -> IngestEligibility: ...

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot: ...
