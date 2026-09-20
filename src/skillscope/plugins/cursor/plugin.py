"""Cursor implementation of the harness ingestion port."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skillscope.application.ports import ConversationRef, DiscoveryContext, Platform
from skillscope.domain.models import (
    ConversationSnapshot,
    EligibilityVerdict,
    IngestEligibility,
    ReadinessBasis,
)
from skillscope.plugins.cursor.parser import build_conversation_snapshot


def _conversation_id(value: object) -> str | None:
    if not isinstance(value, dict) or not isinstance(value.get("payload"), dict):
        return None
    result = value["payload"].get("conversation_id")
    return result if isinstance(result, str) else None


def _spool_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                with suppress(json.JSONDecodeError):
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(value)
    except (OSError, UnicodeError):
        pass
    return records


def _transcript_root(context: DiscoveryContext) -> Path:
    return context.transcript_override or context.home / ".cursor" / "projects"


def _spool_path(context: DiscoveryContext) -> Path:
    if context.spool_override:
        return context.spool_override
    from skillscope.config import default_spool_path

    return context.user_data / default_spool_path().name


def _transcript_candidates(root: Path) -> dict[str, Path]:
    if root.is_file() and root.suffix == ".jsonl":
        return {root.stem: root}
    candidates: dict[str, Path] = {}
    if not root.is_dir():
        return candidates
    for transcript in sorted(root.rglob("*.jsonl")):
        if not transcript.is_file() or "subagents" in transcript.parts:
            continue
        conversation_id = transcript.stem
        if transcript.parent.name != conversation_id:
            continue
        existing = candidates.get(conversation_id)
        if existing is None or (
            existing != transcript.parent and transcript.parent.name == conversation_id
        ):
            candidates[conversation_id] = transcript.parent
    return candidates


def _transcript_files(locator: Path | None) -> list[Path]:
    if locator is None:
        return []
    if locator.is_file():
        return [locator]
    return sorted(locator.glob("*.jsonl")) if locator.is_dir() else []


def _truncated(paths: list[Path]) -> bool:
    for path in paths:
        try:
            lines = [
                line for line in path.read_text(encoding="utf-8").splitlines() if line
            ]
        except (OSError, UnicodeError):
            return True
        if not lines:
            continue
        try:
            value = json.loads(lines[-1])
        except json.JSONDecodeError:
            return True
        if not isinstance(value, dict):
            return True
    return False


def _ref_transcript(conversation: ConversationRef) -> Path | None:
    configured = conversation.extra.get("transcript_dir")
    if isinstance(configured, str):
        return Path(configured)
    for locator in conversation.source_locators:
        if locator.suffix != ".jsonl" or locator.name not in {
            "cursor-hooks.jsonl",
            "cursor-hook-spool.jsonl",
        }:
            return locator
    return None


class CursorPlugin:
    """Discover, inspect, and normalize Cursor conversation evidence."""

    id = "cursor"

    def detect_platform(self) -> Platform:
        if sys.platform.startswith("linux"):
            os_name = "linux"
        elif sys.platform == "darwin":
            os_name = "darwin"
        elif sys.platform.startswith("win"):
            os_name = "win32"
        else:
            os_name = sys.platform
        return Platform(os=os_name, harness=self.id)

    def discover(self, context: DiscoveryContext) -> Iterable[ConversationRef]:
        spool = _spool_path(context)
        transcripts = _transcript_candidates(_transcript_root(context))
        spool_ids = {
            native_id
            for record in _spool_records(spool)
            if (native_id := _conversation_id(record)) is not None
        }
        for native_id in sorted(set(transcripts) | spool_ids):
            transcript = transcripts.get(native_id)
            locators = ([transcript] if transcript else []) + (
                [spool] if native_id in spool_ids else []
            )
            extra: dict[str, object] = {}
            if transcript:
                extra["transcript_dir"] = str(transcript)
            else:
                extra["spool_only"] = True
            yield ConversationRef(
                harness_id=self.id,
                native_conversation_id=native_id,
                source_locators=tuple(locators),
                extra=extra,
            )

    def inspect(
        self,
        conversation: ConversationRef,
        *,
        now: datetime,
        context: DiscoveryContext,
    ) -> IngestEligibility:
        if conversation.harness_id != self.id:
            return IngestEligibility(
                EligibilityVerdict.REJECT,
                reason="Conversation belongs to a different harness.",
            )
        spool = _spool_path(context)
        records = [
            record
            for record in _spool_records(spool)
            if _conversation_id(record) == conversation.native_conversation_id
        ]
        if any(record.get("event_kind") == "session_ended" for record in records):
            return IngestEligibility(
                EligibilityVerdict.READY,
                ReadinessBasis.NATIVE_END,
            )
        files = _transcript_files(_ref_transcript(conversation))
        if not files:
            return IngestEligibility(
                EligibilityVerdict.DEFER,
                reason="Hook evidence has no terminal event or transcript.",
            )
        if _truncated(files):
            return IngestEligibility(
                EligibilityVerdict.DEFER,
                reason="Transcript has a malformed final record.",
            )
        mtimes: list[float] = []
        for path in files:
            try:
                mtimes.append(path.stat().st_mtime)
            except OSError:
                return IngestEligibility(
                    EligibilityVerdict.REJECT,
                    reason="Transcript metadata is unavailable.",
                )
        hook_times: list[float] = []
        for record in records:
            captured_at = record.get("captured_at")
            if not isinstance(captured_at, str):
                continue
            with suppress(ValueError):
                captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=UTC)
                hook_times.append(captured.timestamp())
        if hook_times:
            mtimes.extend(hook_times)
        elif records and spool.is_file():
            with suppress(OSError):
                mtimes.append(spool.stat().st_mtime)
        if not mtimes:
            return IngestEligibility(
                EligibilityVerdict.REJECT,
                reason="Conversation has no readable source.",
            )
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        if now.timestamp() - max(mtimes) < context.grace_seconds:
            return IngestEligibility(
                EligibilityVerdict.DEFER,
                reason="Conversation sources are still within the grace period.",
            )
        return IngestEligibility(
            EligibilityVerdict.READY,
            ReadinessBasis.QUIESCENT,
        )

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot:
        spool = _spool_path(context)
        native_end = any(
            record.get("event_kind") == "session_ended"
            and _conversation_id(record) == conversation.native_conversation_id
            for record in _spool_records(spool)
        )
        snapshot, _ = build_conversation_snapshot(
            conversation.native_conversation_id,
            _ref_transcript(conversation),
            spool,
            readiness_basis=(
                ReadinessBasis.NATIVE_END if native_end else ReadinessBasis.QUIESCENT
            ),
            contract_version=context.contract_version,
            user_skill_roots=(
                str(context.home / ".cursor" / "skills"),
                str(context.home / ".claude" / "skills"),
            ),
        )
        return snapshot
