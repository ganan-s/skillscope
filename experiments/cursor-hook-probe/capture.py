#!/usr/bin/env python3
"""Capture Cursor read hook payloads without affecting the agent operation."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path(__file__).parent / ".local" / "events.jsonl"
VALID_EVENT_KINDS = {
    "session_started",
    "task_submitted",
    "read_succeeded",
    "read_failed",
    "session_ended",
}
GLOB_CHARACTERS = frozenset("*?[")


def read_payload() -> dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    return payload


def snapshot_skill_manifest(
    event_kind: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    if event_kind != "read_succeeded":
        return None

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    raw_path = tool_input.get("file_path", tool_input.get("path"))
    if not isinstance(raw_path, str):
        return None
    if any(character in raw_path for character in GLOB_CHARACTERS):
        return None

    path = Path(raw_path)
    if path.name != "SKILL.md":
        return None

    try:
        body = path.read_bytes()
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


def append_event(event_kind: str, payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "probe_schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "event_kind": event_kind,
        "payload": payload,
        "skill_manifest_snapshot": snapshot_skill_manifest(event_kind, payload),
    }
    with OUTPUT_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True))
        stream.write("\n")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_EVENT_KINDS:
        print(
            f"usage: capture.py <{'|'.join(sorted(VALID_EVENT_KINDS))}>",
            file=sys.stderr,
        )
        return 2

    try:
        append_event(sys.argv[1], read_payload())
    except Exception as error:
        # The probe is observational. It must fail open and leave the original
        # Cursor tool result untouched.
        print(f"skillscope hook probe failed: {error}", file=sys.stderr)
        return 1

    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
