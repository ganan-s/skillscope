"""Normalize Cursor transcripts and hook records into canonical snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    Diagnostic,
    DiagnosticCode,
    EventType,
    Evidence,
    EvidenceQuality,
    PayloadStatus,
    ReadinessBasis,
    SourceBucket,
    SourceRevision,
    TimeProvenance,
)

_GLOBS = frozenset("*?[")
_USER_QUERY = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)


@dataclass(frozen=True)
class _Record:
    value: dict[str, Any]
    position: int
    locator: str
    raw: str


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (result.replace(tzinfo=UTC) if result.tzinfo is None else result).astimezone(
        UTC
    )


def _read_jsonl(
    path: Path | None,
    diagnostics: list[Diagnostic],
    *,
    transcript: bool = False,
) -> list[_Record]:
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        diagnostics.append(
            Diagnostic(
                DiagnosticCode.NATIVE_RECORD_UNSUPPORTED,
                "Native source could not be read.",
                path=path.name,
            )
        )
        return []
    records: list[_Record] = []
    for position, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            diagnostics.append(
                Diagnostic(
                    DiagnosticCode.TRANSCRIPT_TRUNCATED
                    if transcript and position == len(lines)
                    else DiagnosticCode.NATIVE_RECORD_UNSUPPORTED,
                    "Malformed native JSONL record was skipped.",
                    path=path.name,
                    record_position=position,
                )
            )
            continue
        if isinstance(value, dict):
            records.append(_Record(value, position, path.name, raw))
        else:
            diagnostics.append(
                Diagnostic(
                    DiagnosticCode.NATIVE_RECORD_UNSUPPORTED,
                    "Non-object native record was skipped.",
                    path=path.name,
                    record_position=position,
                )
            )
    return records


def _transcript_files(source: Path | None) -> list[Path]:
    if source is None:
        return []
    if source.is_file():
        return [source]
    return sorted(source.glob("*.jsonl")) if source.is_dir() else []


def _path(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    value = tool_input.get("file_path", tool_input.get("path"))
    if not isinstance(value, str) or not value or any(c in value for c in _GLOBS):
        return None
    return value


_READ_TOOLS = frozenset({"Read", "ReadFile"})


def native_content(record: dict[str, Any]) -> object:
    """Return the native content payload from either Cursor transcript shape."""
    message = record.get("message")
    if isinstance(message, dict) and "content" in message:
        return message.get("content")
    return record.get("content")


def native_user_text(record: dict[str, Any]) -> str | None:
    """Extract user-query text from a native transcript record.

    Live Cursor transcripts use `{role, message: {content: [{type, text}]}}`.
    Older records used `{role, content}` as a string or `<user_query>` wrapper.
    """
    content = native_content(record)
    blocks: list[object]
    if isinstance(content, list):
        blocks = content
    elif content is None:
        return None
    else:
        blocks = [content]
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            raw = block
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            raw = block["text"]
        else:
            continue
        match = _USER_QUERY.search(raw)
        text = (match.group(1) if match else raw).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts) if parts else None


def _hook_task_text(payload: dict[str, Any]) -> str | None:
    for key in ("prompt", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for key in ("input", "prompt", "text"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _scalar(value: str) -> str | None:
    value = value.strip()
    if not value or value in {"null", "Null", "NULL", "~"}:
        return None
    if value[:1] in {'"', "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            return None
        if value[0] == '"':
            with suppress(json.JSONDecodeError):
                decoded = json.loads(value)
                return decoded if isinstance(decoded, str) else None
            return None
        return value[1:-1].replace("''", "'")
    if value.startswith(("[", "{", "&", "*", "!")):
        return None
    return value.split(" #", 1)[0].strip() or None


def parse_frontmatter(content: str) -> dict[str, str] | None:
    """Parse string-valued YAML frontmatter without inventing metadata."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    with suppress(StopIteration):
        closing = next(
            i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"
        )
        parsed: dict[str, str] = {}
        index = 1
        while index < closing:
            line = lines[index]
            index += 1
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line[:1].isspace() or ":" not in line:
                return None
            key, raw = line.split(":", 1)
            key = key.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
                return None
            if raw.strip() in {"|", ">"}:
                folded = raw.strip() == ">"
                block: list[str] = []
                while index < closing and (
                    not lines[index].strip() or lines[index][:1].isspace()
                ):
                    block.append(lines[index].strip())
                    index += 1
                value = (" " if folded else "\n").join(block).strip()
            else:
                value = _scalar(raw)
            if value is not None:
                parsed[key] = value
        name = parsed.get("name")
        if name:
            result = {"name": name.strip()}
            if parsed.get("description"):
                result["description"] = parsed["description"].strip()
            return result
    return None


def _normal(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


def infer_source_bucket(
    path: str,
    *,
    workspace_roots: list[str] | tuple[str, ...] = (),
    user_skill_roots: list[str] | tuple[str, ...] = (),
) -> SourceBucket:
    """Infer path provenance lexically, without live filesystem resolution."""
    normal = _normal(path)
    lowered = normal.lower()
    for root in workspace_roots:
        candidate = _normal(root)
        if normal == candidate or normal.startswith(candidate + "/"):
            return SourceBucket.PROJECT
    for root in user_skill_roots:
        candidate = _normal(root)
        if normal == candidate or normal.startswith(candidate + "/"):
            return SourceBucket.USER
    if "/.cursor/skills-cursor/" in lowered:
        return SourceBucket.CURSOR_BUILTIN
    if "/.agents/skills/" in lowered or "/agents/skills/" in lowered:
        return SourceBucket.AGENTS
    if any(
        marker in lowered
        for marker in ("/.cursor/skills/", "/.claude/plugins/", "/.claude/skills/")
    ):
        return SourceBucket.USER
    return SourceBucket.UNKNOWN


def _snapshot(value: object) -> tuple[dict[str, Any], bool]:
    if not isinstance(value, dict) or value.get("status") != "captured":
        reason = value.get("reason") if isinstance(value, dict) else "snapshot_missing"
        return {
            "status": PayloadStatus.UNAVAILABLE.value,
            "content": None,
            "sha256": None,
            "byte_length": None,
            "unavailable_reason": reason,
        }, False
    content = value.get("content")
    if not isinstance(content, str):
        return {
            "status": PayloadStatus.UNAVAILABLE.value,
            "content": None,
            "sha256": None,
            "byte_length": None,
            "unavailable_reason": "content_missing",
        }, False
    body = content.encode()
    return {
        "status": PayloadStatus.CAPTURED.value,
        "content": content,
        "sha256": hashlib.sha256(body).hexdigest(),
        "byte_length": len(body),
        "unavailable_reason": None,
    }, True


def _id(prefix: str, conversation_id: str, source: str) -> str:
    digest = hashlib.sha256(
        f"{prefix}\0{conversation_id}\0{source}".encode()
    ).hexdigest()
    return f"{prefix}-{digest[:24]}"


def _evidence(record: _Record, payload: dict[str, Any]) -> Evidence:
    tool_id = payload.get("tool_use_id")
    return Evidence(
        source_kind="hook",
        native_event_kind="read_succeeded",
        native_event_id=tool_id if isinstance(tool_id, str) else None,
        redacted_locator=record.locator,
        record_position=record.position,
        harness_version=(
            payload.get("cursor_version")
            if isinstance(payload.get("cursor_version"), str)
            else None
        ),
        quality=EvidenceQuality.CONFIRMED,
    )


def build_conversation_snapshot(
    conversation_id: str,
    transcript_dir: Path | None,
    spool_path: Path | None,
    *,
    source_updated_at: datetime | None = None,
    readiness_basis: ReadinessBasis | None = None,
    contract_version: int = CONTRACT_VERSION,
    user_skill_roots: tuple[str, ...] = (),
) -> tuple[ConversationSnapshot, tuple[Diagnostic, ...]]:
    """Build a deterministic complete snapshot from transcript and hook evidence."""
    diagnostics: list[Diagnostic] = []
    transcript_paths = _transcript_files(transcript_dir)
    transcripts = [
        record
        for path in transcript_paths
        for record in _read_jsonl(path, diagnostics, transcript=True)
    ]
    hooks = [
        record
        for record in _read_jsonl(spool_path, diagnostics)
        if isinstance(record.value.get("payload"), dict)
        and record.value["payload"].get("conversation_id") == conversation_id
    ]

    workspaces: list[str] = []
    for record in hooks:
        roots = record.value["payload"].get("workspace_roots")
        if isinstance(roots, list):
            workspaces.extend(
                root
                for root in roots
                if isinstance(root, str) and root not in workspaces
            )

    hook_tasks: list[dict[str, Any]] = []
    for record in hooks:
        payload = record.value["payload"]
        text = _hook_task_text(payload)
        if record.value.get("event_kind") == "task_submitted" and text:
            hook_tasks.append(
                {
                    "text": text,
                    "generation": payload.get("generation_id"),
                    "record": record,
                }
            )
    tasks: list[dict[str, Any]] = []
    used: set[int] = set()
    for record in transcripts:
        if record.value.get("role") != "user":
            continue
        text = native_user_text(record.value)
        if text is None:
            continue
        match = next(
            (
                i
                for i, task in enumerate(hook_tasks)
                if i not in used and task["text"] == text
            ),
            None,
        )
        if match is None:
            tasks.append({"text": text, "record": record})
        else:
            used.add(match)
            tasks.append({**hook_tasks[match], "hook": True})
    tasks.extend(
        {**task, "hook": True} for i, task in enumerate(hook_tasks) if i not in used
    )
    for index, task in enumerate(tasks):
        task["turn"] = index
    generation_turns = {
        task["generation"]: task["turn"]
        for task in tasks
        if isinstance(task.get("generation"), str)
    }

    events: list[CanonicalEvent] = []
    for task in tasks:
        record = task["record"]
        generation = task.get("generation")
        is_hook = bool(task.get("hook"))
        occurred = _time(record.value.get("captured_at")) if is_hook else None
        source = (
            generation
            if isinstance(generation, str)
            else f"{record.locator}:{record.position}"
        )
        events.append(
            CanonicalEvent(
                contract_version,
                _id("task", conversation_id, source),
                EventType.TASK_RECORDED,
                "cursor",
                conversation_id,
                0,
                Evidence(
                    "hook" if is_hook else "transcript",
                    "task_submitted" if is_hook else "user_message",
                    generation if isinstance(generation, str) else None,
                    record.locator,
                    record.position,
                    quality=EvidenceQuality.CONFIRMED,
                ),
                native_turn_id=generation if isinstance(generation, str) else None,
                turn_index=task["turn"],
                occurred_at=occurred,
                time_provenance=(
                    TimeProvenance.COLLECTOR_OBSERVED
                    if occurred
                    else TimeProvenance.MISSING
                ),
                payload={"raw_text": task["text"]},
            )
        )

    outcomes: set[str] = set()
    activations: list[tuple[str, str]] = []
    for record in hooks:
        kind = record.value.get("event_kind")
        payload = record.value["payload"]
        if (
            kind not in {"read_succeeded", "read_failed"}
            or payload.get("tool_name") not in _READ_TOOLS
        ):
            continue
        path = _path(payload)
        tool_id = payload.get("tool_use_id")
        if isinstance(tool_id, str):
            outcomes.add(tool_id)
        if kind == "read_failed":
            diagnostics.append(
                Diagnostic(
                    DiagnosticCode.READ_FAILED,
                    "Cursor reported that a read did not succeed.",
                    path=path,
                    record_position=record.position,
                )
            )
            continue
        if path is None:
            continue
        generation = payload.get("generation_id")
        event_id = (
            tool_id
            if isinstance(tool_id, str) and tool_id
            else _id("read", conversation_id, f"hook:{record.position}")
        )
        occurred = _time(record.value.get("captured_at"))
        common = {
            "contract_version": contract_version,
            "event_id": event_id,
            "harness_id": "cursor",
            "native_conversation_id": conversation_id,
            "sequence": 0,
            "evidence": _evidence(record, payload),
            "native_turn_id": generation if isinstance(generation, str) else None,
            "turn_index": generation_turns.get(generation),
            "occurred_at": occurred,
            "time_provenance": (
                TimeProvenance.COLLECTOR_OBSERVED
                if occurred
                else TimeProvenance.MISSING
            ),
        }
        if PurePath(path).name == "SKILL.md":
            captured, available = _snapshot(record.value.get("skill_manifest_snapshot"))
            event_payload: dict[str, Any] = {
                "path": path,
                "source_bucket": infer_source_bucket(
                    path,
                    workspace_roots=workspaces,
                    user_skill_roots=user_skill_roots,
                ).value,
                "activation_name": "Read",
                "native_tool_use_id": tool_id if isinstance(tool_id, str) else None,
                "activation_id": event_id,
                "payload_snapshot": captured,
            }
            if available:
                frontmatter = parse_frontmatter(captured["content"])
                if frontmatter:
                    event_payload["skill_name"] = frontmatter["name"]
                    if "description" in frontmatter:
                        event_payload["skill_description"] = frontmatter["description"]
                else:
                    diagnostics.append(
                        Diagnostic(
                            DiagnosticCode.FRONTMATTER_INVALID,
                            "Manifest frontmatter is missing or invalid.",
                            path=path,
                            record_position=record.position,
                        )
                    )
            else:
                diagnostics.append(
                    Diagnostic(
                        DiagnosticCode.PAYLOAD_UNAVAILABLE,
                        "Confirmed manifest read could not be snapshotted.",
                        path=path,
                        record_position=record.position,
                    )
                )
            events.append(
                CanonicalEvent(
                    event_type=EventType.SKILL_ACTIVATED,
                    payload=event_payload,
                    **common,
                )
            )
            activations.append((_normal(str(PurePath(path).parent)), event_id))
            continue
        parent = next(
            (
                activation_id
                for directory, activation_id in reversed(activations)
                if _normal(path).startswith(directory + "/")
            ),
            None,
        )
        if parent:
            captured, available = _snapshot(record.value.get("resource_snapshot"))
            if not available:
                diagnostics.append(
                    Diagnostic(
                        DiagnosticCode.PAYLOAD_UNAVAILABLE,
                        "Confirmed resource read could not be snapshotted.",
                        path=path,
                        record_position=record.position,
                    )
                )
            events.append(
                CanonicalEvent(
                    event_type=EventType.SKILL_RESOURCE_READ,
                    payload={
                        "parent_activation_id": parent,
                        "path": path,
                        "native_tool_use_id": tool_id,
                        "payload_snapshot": captured,
                    },
                    **common,
                )
            )

    for record in transcripts:
        content = native_content(record.value)
        if record.value.get("role") != "assistant" or not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            if item.get("name") in _READ_TOOLS and item.get("id") not in outcomes:
                tool_input = item.get("input")
                candidate = (
                    tool_input.get("path") if isinstance(tool_input, dict) else None
                )
                diagnostics.append(
                    Diagnostic(
                        DiagnosticCode.READ_OUTCOME_UNKNOWN,
                        "Offline transcript read has no confirmed outcome.",
                        path=candidate if isinstance(candidate, str) else None,
                        record_position=record.position,
                    )
                )

    starts = [r for r in hooks if r.value.get("event_kind") == "session_started"]
    ends = [r for r in hooks if r.value.get("event_kind") == "session_ended"]
    started_at = _time(starts[0].value.get("captured_at")) if starts else None
    ended_at = _time(ends[-1].value.get("captured_at")) if ends else None
    basis = readiness_basis or (
        ReadinessBasis.NATIVE_END if ends else ReadinessBasis.QUIESCENT
    )
    digest = hashlib.sha256()
    for path in transcript_paths:
        with suppress(OSError):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    for record in hooks:
        digest.update(record.raw.encode())
        digest.update(b"\n")
    revision = digest.hexdigest()
    if source_updated_at is None:
        times = [
            time for record in hooks if (time := _time(record.value.get("captured_at")))
        ]
        for path in transcript_paths:
            with suppress(OSError):
                times.append(datetime.fromtimestamp(path.stat().st_mtime, UTC))
        source_updated_at = max(times, default=datetime(1970, 1, 1, tzinfo=UTC))
    elif source_updated_at.tzinfo is None:
        source_updated_at = source_updated_at.replace(tzinfo=UTC)
    else:
        source_updated_at = source_updated_at.astimezone(UTC)
    events.append(
        CanonicalEvent(
            contract_version,
            _id("session", conversation_id, f"{basis.value}:{revision}"),
            EventType.SESSION_CLOSED,
            "cursor",
            conversation_id,
            0,
            Evidence(
                "hook" if ends else "transcript",
                "session_ended" if ends else "quiescence",
                redacted_locator=ends[-1].locator if ends else "transcript",
                record_position=ends[-1].position if ends else None,
                quality=EvidenceQuality.CONFIRMED if ends else EvidenceQuality.INFERRED,
            ),
            occurred_at=ended_at,
            time_provenance=(
                TimeProvenance.COLLECTOR_OBSERVED
                if ended_at
                else TimeProvenance.MISSING
            ),
            payload={
                "readiness_basis": basis.value,
                "source_revision": revision,
                "source_updated_at": source_updated_at.isoformat(),
                "native_end_reason": (
                    ends[-1].value["payload"].get("end_reason") if ends else None
                ),
                "workspace_paths": workspaces,
            },
        )
    )
    events = [replace(event, sequence=index) for index, event in enumerate(events)]
    if not workspaces:
        diagnostics.append(
            Diagnostic(
                DiagnosticCode.METADATA_MISSING,
                "Workspace metadata was not available.",
            )
        )
    snapshot = ConversationSnapshot(
        contract_version,
        "cursor",
        conversation_id,
        SourceRevision(revision, source_updated_at),
        basis,
        tuple(events),
        tuple(diagnostics),
        tasks[0]["text"] if tasks else None,
        tuple(workspaces),
        started_at,
        ended_at,
    )
    return snapshot, tuple(diagnostics)
