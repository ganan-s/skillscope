"""Fail-open Cursor hook collector.

This is a command-line entry point invoked by Cursor hooks.  It reads a JSON
payload from stdin, sanitises it, and appends a single JSONL record to the
spool file.  For confirmed successful SKILL.md reads it also captures a
contemporaneous body snapshot and SHA-256 hash.

Exit behaviour:
- Always prints ``{}`` to stdout so Cursor sees no injected context.
- Never raises to the caller; errors go to stderr and exit 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GLOB_CHARACTERS = frozenset("*?[")

VALID_EVENT_KINDS = {
    "session_started",
    "task_submitted",
    "read_succeeded",
    "read_failed",
    "session_ended",
}

# Fields stripped from every hook payload before spooling.
_SENSITIVE_FIELDS = frozenset({
    "user_email",
    "model",
    "tool_output",         # may contain arbitrary file content
})

# Fields retained in the sanitised record.
_RETAINED_FIELDS = frozenset({
    "conversation_id",
    "session_id",
    "generation_id",
    "tool_use_id",
    "tool_name",
    "tool_input",
    "cursor_version",
    "duration",
    "hook_event_name",
    "workspace_roots",
    "transcript_path",
    # failure-specific
    "failure_type",
    "error_message",
    "is_interrupt",
})


def _resolve_spool_path() -> Path:
    override = os.environ.get("SKILLSCOPE_SPOOL_PATH")
    if override:
        return Path(override)
    from skillscope.config import default_spool_path
    return default_spool_path()


def _sanitise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields needed by the adapter; drop PII and secrets."""
    return {k: v for k, v in payload.items() if k in _RETAINED_FIELDS}


def _extract_file_path(payload: dict[str, Any]) -> str | None:
    """Return the concrete file path from the tool input, or None."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path", tool_input.get("path"))
    if not isinstance(raw, str):
        return None
    if any(c in raw for c in GLOB_CHARACTERS):
        return None
    return raw


def snapshot_skill_manifest(
    event_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Capture a contemporaneous SKILL.md body when the read succeeded."""
    if event_kind != "read_succeeded":
        return None

    raw_path = _extract_file_path(payload)
    if raw_path is None:
        return None

    path = Path(raw_path)
    if path.name != "SKILL.md":
        return None

    try:
        body = path.read_bytes()
        content = body.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "status": "unavailable",
            "path": raw_path,
            "reason": type(exc).__name__,
        }

    return {
        "status": "captured",
        "path": raw_path,
        "sha256": hashlib.sha256(body).hexdigest(),
        "byte_length": len(body),
        "content": content,
    }


def build_record(
    event_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build the spool record from a raw hook payload."""
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "event_kind": event_kind,
        "payload": _sanitise_payload(payload),
        "skill_manifest_snapshot": snapshot_skill_manifest(event_kind, payload),
    }


def append_to_spool(
    record: dict[str, Any],
    spool_path: Path | None = None,
) -> None:
    """Append one JSONL record to the spool file."""
    dest = spool_path or _resolve_spool_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True))
        f.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in VALID_EVENT_KINDS:
        print(
            f"usage: collector.py <{'|'.join(sorted(VALID_EVENT_KINDS))}>",
            file=sys.stderr,
        )
        return 2

    event_kind = args[0]
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be a JSON object")
        record = build_record(event_kind, payload)
        append_to_spool(record)
    except Exception as exc:
        print(f"skillscope collector failed: {exc}", file=sys.stderr)
        return 1

    # Fail-open: empty object means no injected context.
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
