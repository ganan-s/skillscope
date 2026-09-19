"""Parse Cursor transcripts and hook spool records into canonical events.

Merge rules (from docs/03-ingestion-contract.md):
- Confirmed hook outcome wins over offline request.
- Hook workspace roots win over lossy project-directory slug.
- Offline Read requests alone are ``read_outcome_unknown``, never activation.
- Activations require confirmed success + exact case-sensitive ``SKILL.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    Diagnostic,
    DiagnosticCode,
    Evidence,
    EvidenceQuality,
    EventType,
    PayloadSnapshot,
    PayloadStatus,
    ReadinessBasis,
    SourceBucket,
    SourceRevision,
    TimeProvenance,
)

GLOB_CHARACTERS = frozenset("*?[")

# Regex to extract <user_query> content from Cursor transcript user messages.
_USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL
)


# ---------------------------------------------------------------------------
# Source bucket inference
# ---------------------------------------------------------------------------

def infer_source_bucket(
    path: str,
    workspace_roots: list[str] | None = None,
) -> SourceBucket:
    """Infer a display-level source bucket from a path string."""
    norm = path.replace("\\", "/")
    if "/.cursor/skills-cursor/" in norm or "/.cursor/skills/" in norm:
        return SourceBucket.CURSOR_BUILTIN
    if "/.claude/plugins/" in norm:
        return SourceBucket.USER
    if "/.codex/skills/" in norm:
        return SourceBucket.USER
    # User-level skill directories
    home_markers = ("/Users/", "/home/", "C:/Users/")
    for marker in home_markers:
        if marker in norm:
            # Check if it's under a workspace
            if workspace_roots:
                for wr in workspace_roots:
                    wr_norm = wr.replace("\\", "/")
                    if norm.startswith(wr_norm):
                        return SourceBucket.PROJECT
            # Check agents dir convention
            if "/AGENTS.md" in norm:
                return SourceBucket.AGENTS
            if "/.cursor/rules/" in norm:
                return SourceBucket.PROJECT
    if workspace_roots:
        for wr in workspace_roots:
            wr_norm = wr.replace("\\", "/")
            if norm.startswith(wr_norm):
                return SourceBucket.PROJECT
    return SourceBucket.UNKNOWN


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict[str, str] | None:
    """Extract name and description from YAML frontmatter.

    Only handles the simple scalar fields the contract needs.
    Returns None if frontmatter is missing or malformed.
    """
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    yaml_block = parts[1].strip()
    if not yaml_block:
        return None
    result: dict[str, str] = {}
    for line in yaml_block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in ("name", "description") and value:
            result[key] = value
    return result if "name" in result else None


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def _parse_transcript_records(jsonl_path: Path) -> list[dict[str, Any]]:
    """Read a JSONL transcript file into a list of records."""
    records: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _extract_user_query(text: str) -> str:
    """Extract <user_query> content or fall back to raw text."""
    match = _USER_QUERY_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_user_tasks(
    records: list[dict[str, Any]],
    conversation_id: str,
) -> tuple[list[CanonicalEvent], list[Diagnostic]]:
    """Extract task.recorded events from transcript user messages."""
    events: list[CanonicalEvent] = []
    diagnostics: list[Diagnostic] = []
    seq = 0
    turn_idx = 0

    for i, rec in enumerate(records):
        role = rec.get("role")
        if role != "user":
            continue
        turn_idx += 1
        content = rec.get("content", "")
        if isinstance(content, list):
            # Multi-part content: extract text items
            text_parts = [
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = "\n".join(text_parts)
        if not isinstance(content, str) or not content.strip():
            continue

        raw_text = _extract_user_query(content)
        if not raw_text:
            continue

        seq += 1
        event_id = f"{conversation_id}:task:{seq}"
        events.append(CanonicalEvent(
            contract_version=CONTRACT_VERSION,
            event_id=event_id,
            event_type=EventType.TASK_RECORDED,
            harness_id="cursor",
            native_conversation_id=conversation_id,
            sequence=seq,
            evidence=Evidence(
                source_kind="transcript",
                native_event_kind="user_message",
                record_position=i,
                quality=EvidenceQuality.CONFIRMED,
            ),
            turn_index=turn_idx,
            payload={"raw_text": raw_text},
        ))

    return events, diagnostics


def _find_offline_read_requests(
    records: list[dict[str, Any]],
    conversation_id: str,
    start_seq: int,
) -> tuple[list[Diagnostic], int]:
    """Identify offline Read requests that have no confirmed outcome.

    These produce diagnostics, never activations.
    """
    diagnostics: list[Diagnostic] = []
    seq = start_seq

    for i, rec in enumerate(records):
        role = rec.get("role")
        if role != "assistant":
            continue
        content = rec.get("content", [])
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            tool_name = item.get("name", "")
            if tool_name not in ("Read", "ReadFile"):
                continue
            inp = item.get("input", {})
            path = inp.get("path", inp.get("file_path", ""))
            if not isinstance(path, str):
                continue
            if Path(path).name == "SKILL.md":
                diagnostics.append(Diagnostic(
                    code=DiagnosticCode.READ_OUTCOME_UNKNOWN,
                    message="offline Read request with no confirmed outcome",
                    path=path,
                    record_position=i,
                ))

    return diagnostics, seq


# ---------------------------------------------------------------------------
# Hook spool parsing
# ---------------------------------------------------------------------------

def _parse_spool_records(
    spool_path: Path,
    conversation_id: str,
) -> list[dict[str, Any]]:
    """Read and filter spool records for a specific conversation."""
    if not spool_path.exists():
        return []
    results: list[dict[str, Any]] = []
    with spool_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = rec.get("payload", {})
            cid = payload.get("conversation_id", payload.get("session_id"))
            if cid == conversation_id:
                results.append(rec)
    return results


def _hook_activations(
    spool_records: list[dict[str, Any]],
    conversation_id: str,
    workspace_roots: list[str] | None,
    start_seq: int,
) -> tuple[list[CanonicalEvent], list[Diagnostic], int]:
    """Build skill.activated events from confirmed hook reads."""
    events: list[CanonicalEvent] = []
    diagnostics: list[Diagnostic] = []
    seq = start_seq

    for rec in spool_records:
        event_kind = rec.get("event_kind")
        payload = rec.get("payload", {})
        snapshot_data = rec.get("skill_manifest_snapshot")

        if event_kind == "read_failed":
            tool_input = payload.get("tool_input", {})
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            if isinstance(file_path, str) and Path(file_path).name == "SKILL.md":
                diagnostics.append(Diagnostic(
                    code=DiagnosticCode.READ_FAILED,
                    message=payload.get("error_message", "read failed"),
                    path=file_path,
                ))
            continue

        if event_kind != "read_succeeded":
            continue

        # Only SKILL.md activations
        if snapshot_data is None:
            continue

        skill_path = snapshot_data.get("path", "")
        if not skill_path or Path(skill_path).name != "SKILL.md":
            continue

        # Build payload snapshot
        if snapshot_data.get("status") == "captured":
            ps = PayloadSnapshot(
                status=PayloadStatus.CAPTURED,
                content=snapshot_data.get("content"),
                sha256=snapshot_data.get("sha256"),
                byte_length=snapshot_data.get("byte_length"),
            )
            fm = parse_frontmatter(snapshot_data.get("content", ""))
            if fm is None and snapshot_data.get("content"):
                diagnostics.append(Diagnostic(
                    code=DiagnosticCode.FRONTMATTER_INVALID,
                    message="captured manifest lacks valid frontmatter name",
                    path=skill_path,
                ))
        else:
            ps = PayloadSnapshot(
                status=PayloadStatus.UNAVAILABLE,
                unavailable_reason=snapshot_data.get("reason", "unknown"),
            )
            fm = None
            diagnostics.append(Diagnostic(
                code=DiagnosticCode.PAYLOAD_UNAVAILABLE,
                message="confirmed activation but payload unavailable",
                path=skill_path,
            ))

        seq += 1
        tool_use_id = payload.get("tool_use_id")
        generation_id = payload.get("generation_id")
        event_id = tool_use_id or f"{conversation_id}:activation:{seq}"

        captured_at_str = rec.get("captured_at")
        occurred_at = None
        time_prov = TimeProvenance.MISSING
        if captured_at_str:
            try:
                occurred_at = datetime.fromisoformat(captured_at_str)
                time_prov = TimeProvenance.COLLECTOR_OBSERVED
            except (ValueError, TypeError):
                pass

        event_payload: dict[str, Any] = {
            "path": skill_path,
            "source_bucket": infer_source_bucket(
                skill_path, workspace_roots
            ).value,
            "tool_name": payload.get("tool_name", "Read"),
        }
        if fm:
            event_payload["skill_name"] = fm.get("name")
            event_payload["skill_description"] = fm.get("description")
        event_payload["payload_snapshot"] = {
            "status": ps.status.value,
            "sha256": ps.sha256,
            "byte_length": ps.byte_length,
        }
        if ps.status == PayloadStatus.UNAVAILABLE:
            event_payload["payload_snapshot"]["unavailable_reason"] = (
                ps.unavailable_reason
            )

        events.append(CanonicalEvent(
            contract_version=CONTRACT_VERSION,
            event_id=event_id,
            event_type=EventType.SKILL_ACTIVATED,
            harness_id="cursor",
            native_conversation_id=conversation_id,
            sequence=seq,
            evidence=Evidence(
                source_kind="hook",
                native_event_kind="postToolUse",
                native_event_id=tool_use_id,
                harness_version=payload.get("cursor_version"),
                quality=EvidenceQuality.CONFIRMED,
            ),
            native_turn_id=generation_id,
            occurred_at=occurred_at,
            time_provenance=time_prov,
            payload=event_payload,
        ))

    return events, diagnostics, seq


# ---------------------------------------------------------------------------
# Session lifecycle from hook spool
# ---------------------------------------------------------------------------

def _extract_session_metadata(
    spool_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pull session-level metadata from hook spool records."""
    meta: dict[str, Any] = {
        "workspace_roots": [],
        "has_session_end": False,
        "end_reason": None,
        "title": None,
    }
    for rec in spool_records:
        kind = rec.get("event_kind")
        payload = rec.get("payload", {})
        if kind == "session_started":
            roots = payload.get("workspace_roots", [])
            if roots:
                meta["workspace_roots"] = roots
        elif kind == "session_ended":
            meta["has_session_end"] = True
        elif kind == "task_submitted":
            # Use first task as title fallback
            if meta["title"] is None:
                text = payload.get("tool_input", {}).get("input", "")
                if isinstance(text, str) and text.strip():
                    meta["title"] = text.strip()[:120]
    return meta


# ---------------------------------------------------------------------------
# Full snapshot assembly
# ---------------------------------------------------------------------------

def build_conversation_snapshot(
    conversation_id: str,
    transcript_path: Path | None,
    spool_path: Path | None,
    *,
    source_updated_at: datetime | None = None,
) -> tuple[ConversationSnapshot, list[Diagnostic]]:
    """Assemble a complete canonical snapshot from available sources.

    Returns the snapshot and all diagnostics (including non-fatal ones).
    """
    all_events: list[CanonicalEvent] = []
    all_diagnostics: list[Diagnostic] = []
    workspace_roots: list[str] | None = None

    # 1. Parse hook spool for session metadata and activations
    spool_records: list[dict[str, Any]] = []
    if spool_path and spool_path.exists():
        spool_records = _parse_spool_records(spool_path, conversation_id)

    session_meta = _extract_session_metadata(spool_records)
    workspace_roots = session_meta.get("workspace_roots") or None

    # 2. Parse transcript for user tasks
    transcript_records: list[dict[str, Any]] = []
    if transcript_path and transcript_path.exists():
        jsonl_files = list(transcript_path.glob("*.jsonl")) if transcript_path.is_dir() else [transcript_path]
        for jf in sorted(jsonl_files):
            transcript_records.extend(_parse_transcript_records(jf))

    task_events, task_diags = _extract_user_tasks(
        transcript_records, conversation_id
    )
    all_events.extend(task_events)
    all_diagnostics.extend(task_diags)

    # 3. Offline read diagnostics
    read_diags, _ = _find_offline_read_requests(
        transcript_records, conversation_id, len(all_events)
    )
    all_diagnostics.extend(read_diags)

    # 4. Hook-confirmed activations
    activation_events, activation_diags, _ = _hook_activations(
        spool_records,
        conversation_id,
        workspace_roots,
        start_seq=len(all_events),
    )
    all_events.extend(activation_events)
    all_diagnostics.extend(activation_diags)

    # 5. Determine readiness basis
    readiness = ReadinessBasis.NATIVE_END if session_meta["has_session_end"] else ReadinessBasis.QUIESCENT

    # 6. Source revision
    now = source_updated_at or datetime.now(timezone.utc)
    content_for_hash = json.dumps(
        [e.to_dict() for e in all_events], sort_keys=True
    )
    revision_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]

    # Session closed event
    session_closed = CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id=f"{conversation_id}:session_closed",
        event_type=EventType.SESSION_CLOSED,
        harness_id="cursor",
        native_conversation_id=conversation_id,
        sequence=0,
        evidence=Evidence(
            source_kind="hook" if session_meta["has_session_end"] else "transcript",
            native_event_kind="sessionEnd" if session_meta["has_session_end"] else "quiescent",
            quality=EvidenceQuality.CONFIRMED if session_meta["has_session_end"] else EvidenceQuality.INFERRED,
        ),
        occurred_at=now,
        time_provenance=TimeProvenance.DERIVED,
        payload={
            "readiness_basis": readiness.value,
            "revision": revision_hash,
        },
    )

    # Re-sequence: session_closed first, then tasks, then activations
    ordered: list[CanonicalEvent] = [session_closed]
    for i, evt in enumerate(all_events):
        ordered.append(CanonicalEvent(
            contract_version=evt.contract_version,
            event_id=evt.event_id,
            event_type=evt.event_type,
            harness_id=evt.harness_id,
            native_conversation_id=evt.native_conversation_id,
            sequence=i + 1,
            evidence=evt.evidence,
            native_turn_id=evt.native_turn_id,
            turn_index=evt.turn_index,
            occurred_at=evt.occurred_at,
            time_provenance=evt.time_provenance,
            payload=evt.payload,
        ))

    # Title fallback: first task text
    title = session_meta.get("title")
    if not title and task_events:
        raw = task_events[0].payload.get("raw_text", "")
        if raw:
            title = raw[:120]

    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id=conversation_id,
        source_revision=SourceRevision(
            revision=revision_hash,
            updated_at=now,
        ),
        readiness_basis=readiness,
        events=tuple(ordered),
        diagnostics=tuple(all_diagnostics),
        title=title,
        workspace_paths=tuple(workspace_roots or []),
    )

    return snapshot, all_diagnostics
