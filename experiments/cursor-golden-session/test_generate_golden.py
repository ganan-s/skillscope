"""Tests for local golden-session generation from synthetic collector output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from generate_golden import (
    STABLE_CONVERSATION_ID,
    STABLE_PROMPT,
    STABLE_SKILL_PATH,
    GoldenGenerationError,
    generate_golden,
    install_hooks,
)

PROBE = (
    Path(__file__).resolve().parent / "fixtures" / "probe-skill" / "SKILL.md"
).read_bytes()


def _record(event_kind: str, payload: dict, **extra) -> dict:
    rec = {
        "schema_version": 1,
        "captured_at": "2026-09-19T10:00:00+00:00",
        "event_kind": event_kind,
        "payload": payload,
        "skill_manifest_snapshot": None,
        "resource_snapshot": None,
    }
    rec.update(extra)
    return rec


def _complete_spool(tmp_path: Path) -> Path:
    skill = tmp_path / "real" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_bytes(PROBE)
    native_id = "abc-native-id"
    records = [
        _record(
            "session_started",
            {
                "conversation_id": native_id,
                "session_id": native_id,
                "workspace_roots": [str(tmp_path)],
                "cursor_version": "3.21.13",
            },
        ),
        _record(
            "task_submitted",
            {
                "conversation_id": native_id,
                "generation_id": "gen-native",
                "tool_input": {"input": "please load skills from disk"},
            },
        ),
        _record(
            "read_succeeded",
            {
                "conversation_id": native_id,
                "generation_id": "gen-native",
                "tool_use_id": "tool-a",
                "tool_name": "Read",
                "tool_input": {"file_path": str(skill)},
                "cursor_version": "3.21.13",
            },
            skill_manifest_snapshot={
                "status": "captured",
                "path": str(skill),
                "sha256": hashlib.sha256(PROBE).hexdigest(),
                "byte_length": len(PROBE),
                "content": PROBE.decode(),
            },
        ),
        _record(
            "read_succeeded",
            {
                "conversation_id": native_id,
                "generation_id": "gen-native",
                "tool_use_id": "tool-b",
                "tool_name": "Read",
                "tool_input": {"file_path": str(skill)},
                "cursor_version": "3.21.13",
            },
            skill_manifest_snapshot={
                "status": "captured",
                "path": str(skill),
                "sha256": hashlib.sha256(PROBE).hexdigest(),
                "byte_length": len(PROBE),
                "content": PROBE.decode(),
            },
        ),
        _record(
            "read_failed",
            {
                "conversation_id": native_id,
                "generation_id": "gen-native",
                "tool_use_id": "tool-c",
                "tool_name": "Read",
                "tool_input": {"file_path": str(tmp_path / "missing" / "SKILL.md")},
                "failure_type": "error",
                "error_message": "File not found",
                "is_interrupt": False,
            },
        ),
        _record(
            "session_ended",
            {
                "conversation_id": native_id,
                "session_id": native_id,
                "end_reason": "user",
            },
        ),
    ]
    spool = tmp_path / "raw-spool.jsonl"
    spool.write_text("".join(json.dumps(record) + "\n" for record in records))
    return spool


def _transcript(tmp_path: Path, native_id: str = "abc-native-id") -> Path:
    path = tmp_path / "agent-transcripts" / native_id / f"{native_id}.jsonl"
    path.parent.mkdir(parents=True)
    records = [
        {
            "role": "user",
            "content": "<user_query>\nplease load skills from disk\n</user_query>",
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "secret model thoughts"},
                {
                    "type": "tool_use",
                    "id": "tool-a",
                    "name": "Read",
                    "input": {"path": str(tmp_path / "real" / "SKILL.md")},
                },
            ],
        },
        {"type": "turn_ended", "status": "success"},
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def test_generate_when_capture_is_complete_writes_stable_golden(tmp_path: Path) -> None:
    spool = _complete_spool(tmp_path)
    transcript = _transcript(tmp_path)
    output = tmp_path / "golden"

    generate_golden(
        spool_path=spool,
        transcripts=transcript,
        output=output,
        home=tmp_path,
    )

    expected = json.loads((output / "expected.json").read_text())
    assert expected["conversation_id"] == STABLE_CONVERSATION_ID
    assert expected["task_text"] == STABLE_PROMPT
    assert expected["activation_ids"] == ["tu-success-1", "tu-success-2"]
    assert expected["canonical_event_types"]["skill.activated"] == 2

    hooks = [
        json.loads(line)
        for line in (output / "hooks.jsonl").read_text().splitlines()
        if line
    ]
    assert [record["event_kind"] for record in hooks] == [
        "session_started",
        "task_submitted",
        "read_succeeded",
        "read_succeeded",
        "read_failed",
        "session_ended",
    ]
    assert all(
        record["payload"]["conversation_id"] == STABLE_CONVERSATION_ID
        for record in hooks
    )
    assert hooks[2]["payload"]["tool_input"]["file_path"] == STABLE_SKILL_PATH
    raw_hooks = (output / "hooks.jsonl").read_text()
    assert str(tmp_path) not in raw_hooks
    assert "please load skills from disk" not in raw_hooks

    transcript_out = (
        output
        / "transcripts"
        / STABLE_CONVERSATION_ID
        / f"{STABLE_CONVERSATION_ID}.jsonl"
    ).read_text()
    assert "secret model thoughts" not in transcript_out
    assert STABLE_PROMPT in transcript_out
    assert "tu-success-1" in transcript_out


def test_generate_when_session_end_missing_lists_required_kinds(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "raw-spool.jsonl"
    spool.write_text(
        json.dumps(
            _record(
                "session_started",
                {"conversation_id": "c1", "session_id": "c1"},
            )
        )
        + "\n"
    )
    with pytest.raises(GoldenGenerationError, match="session_ended"):
        generate_golden(spool_path=spool, transcripts=tmp_path, output=tmp_path / "out")


def test_generate_when_spool_missing_explains_capture_steps(tmp_path: Path) -> None:
    missing = tmp_path / "raw-spool.jsonl"
    with pytest.raises(GoldenGenerationError, match="--install-hooks"):
        generate_golden(
            spool_path=missing, transcripts=tmp_path, output=tmp_path / "out"
        )


def test_install_hooks_when_destination_is_empty_writes_example(tmp_path: Path) -> None:
    destination = tmp_path / ".cursor" / "hooks.json"
    written = install_hooks(hooks_path=destination)
    assert written == destination
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert "sessionStart" in payload["hooks"]
    assert "capture_hook.py" in payload["hooks"]["sessionStart"][0]["command"]
