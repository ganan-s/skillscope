"""Privacy-conscious, fail-open collector for Cursor hook events."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VALID_EVENT_KINDS = {
    "session_started",
    "task_submitted",
    "read_succeeded",
    "read_failed",
    "session_ended",
}
_GLOB_CHARACTERS = frozenset("*?[")
_SAFE_FIELDS = {
    "conversation_id",
    "session_id",
    "generation_id",
    "tool_use_id",
    "tool_name",
    "tool_input",
    "workspace_roots",
    "cursor_version",
    "failure_type",
    "error_message",
    "is_interrupt",
    "end_reason",
}
_SAFE_TOOL_INPUT_FIELDS = {"file_path", "path", "input"}


def _resolve_spool_path() -> Path:
    override = os.environ.get("SKILLSCOPE_SPOOL_PATH")
    if override:
        return Path(override)
    from skillscope.config import default_spool_path

    return default_spool_path()


def _concrete_path(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw_path = tool_input.get("file_path", tool_input.get("path"))
    if not isinstance(raw_path, str) or not raw_path:
        return None
    if any(character in raw_path for character in _GLOB_CHARACTERS):
        return None
    return raw_path


def _snapshot_path(raw_path: str) -> dict[str, Any]:
    try:
        body = Path(raw_path).read_bytes()
        content = body.decode("utf-8")
    except (OSError, UnicodeError) as error:
        return {
            "status": "unavailable",
            "path": raw_path,
            "reason": type(error).__name__,
        }
    return {
        "status": "captured",
        "path": raw_path,
        "sha256": hashlib.sha256(body).hexdigest(),
        "byte_length": len(body),
        "content": content,
    }


def snapshot_skill_manifest(
    event_kind: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """Snapshot an exact manifest immediately after a successful read."""
    if event_kind != "read_succeeded":
        return None
    raw_path = _concrete_path(payload)
    if raw_path is None or Path(raw_path).name != "SKILL.md":
        return None
    return _snapshot_path(raw_path)


def _snapshot_resource(
    event_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Snapshot a concrete non-manifest read for later parent validation."""
    if event_kind != "read_succeeded":
        return None
    raw_path = _concrete_path(payload)
    if raw_path is None or Path(raw_path).name == "SKILL.md":
        return None
    return _snapshot_path(raw_path)


def _sanitise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy only contract-relevant hook fields into the local spool."""
    clean: dict[str, Any] = {}
    for key in _SAFE_FIELDS:
        value = payload.get(key)
        if key == "tool_input":
            if isinstance(value, dict):
                safe_input = {
                    input_key: value[input_key]
                    for input_key in _SAFE_TOOL_INPUT_FIELDS
                    if isinstance(value.get(input_key), str)
                }
                if safe_input:
                    clean[key] = safe_input
        elif key == "workspace_roots":
            if isinstance(value, list):
                clean[key] = [root for root in value if isinstance(root, str)]
        elif value is not None and isinstance(value, (str, bool, int, float)):
            clean[key] = value
    return clean


def build_record(
    event_kind: str,
    payload: dict[str, Any],
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Build one versioned and sanitised collector record."""
    if event_kind not in VALID_EVENT_KINDS:
        raise ValueError(f"unsupported Cursor event kind: {event_kind}")
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    return {
        "schema_version": 1,
        "captured_at": (captured_at or datetime.now(UTC)).isoformat(),
        "event_kind": event_kind,
        "payload": _sanitise_payload(payload),
        "skill_manifest_snapshot": snapshot_skill_manifest(event_kind, payload),
        "resource_snapshot": _snapshot_resource(event_kind, payload),
    }


def append_to_spool(
    record: dict[str, Any],
    spool_path: Path | None = None,
) -> None:
    """Append one record to a permission-restricted JSONL spool."""
    destination = spool_path or _resolve_spool_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
    with suppress(OSError):
        os.chmod(destination, 0o600)


def main(argv: list[str] | None = None) -> int:
    """Collect one hook payload without injecting context into Cursor."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in VALID_EVENT_KINDS:
        print(
            f"usage: collector.py <{'|'.join(sorted(VALID_EVENT_KINDS))}>",
            file=sys.stderr,
        )
        return 2
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be a JSON object")
        append_to_spool(build_record(args[0], payload))
    except Exception as error:
        print(f"skillscope collector failed: {error}", file=sys.stderr)
        return 1
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
