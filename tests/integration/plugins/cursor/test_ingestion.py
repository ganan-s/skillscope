from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from skillscope.domain.models import DiagnosticCode, EligibilityVerdict, EventType
from skillscope.plugins.base import ConversationRef, DiscoveryContext
from skillscope.plugins.cursor.parser import build_conversation_snapshot
from skillscope.plugins.cursor.plugin import CursorPlugin


def hook(
    kind: str,
    *,
    tool_id: str,
    path: str,
    snapshot: dict | None,
) -> dict:
    return {
        "schema_version": 1,
        "captured_at": "2026-09-19T12:00:00+00:00",
        "event_kind": kind,
        "payload": {
            "conversation_id": "conversation-1",
            "generation_id": "generation-1",
            "tool_use_id": tool_id,
            "tool_name": "Read",
            "tool_input": {"file_path": path},
        },
        "skill_manifest_snapshot": (snapshot if path.endswith("/SKILL.md") else None),
        "resource_snapshot": (snapshot if not path.endswith("/SKILL.md") else None),
    }


def payload(content: str) -> dict:
    return {
        "status": "captured",
        "content": content,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "byte_length": len(content.encode()),
    }


def write_spool(tmp_path: Path, records: list[dict]) -> Path:
    spool = tmp_path / "hooks.jsonl"
    spool.write_text(
        "".join(f"{json.dumps(record)}\n" for record in records),
        encoding="utf-8",
    )
    return spool


def test_parser_with_repeated_activation_and_resource_preserves_occurrences(
    tmp_path: Path,
) -> None:
    manifest = payload("---\nname: testing\ndescription: Test guidance\n---\n")
    spool = write_spool(
        tmp_path,
        [
            hook(
                "read_succeeded",
                tool_id="activation-1",
                path="/skills/testing/SKILL.md",
                snapshot=manifest,
            ),
            hook(
                "read_succeeded",
                tool_id="resource-1",
                path="/skills/testing/reference.md",
                snapshot=payload("Use pytest."),
            ),
            hook(
                "read_succeeded",
                tool_id="activation-2",
                path="/skills/testing/SKILL.md",
                snapshot=manifest,
            ),
        ],
    )

    snapshot, _ = build_conversation_snapshot("conversation-1", None, spool)

    activations = [
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATED
    ]
    resources = [
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_RESOURCE_READ
    ]
    assert [event.event_id for event in activations] == [
        "activation-1",
        "activation-2",
    ]
    assert resources[0].payload["parent_activation_id"] == "activation-1"
    assert resources[0].payload["payload_snapshot"]["content"] == "Use pytest."


def test_parser_with_failed_read_emits_diagnostic_not_activation(
    tmp_path: Path,
) -> None:
    spool = write_spool(
        tmp_path,
        [
            hook(
                "read_failed",
                tool_id="failed-1",
                path="/skills/testing/SKILL.md",
                snapshot=None,
            )
        ],
    )

    snapshot, diagnostics = build_conversation_snapshot(
        "conversation-1",
        None,
        spool,
    )

    assert not any(
        event.event_type == EventType.SKILL_ACTIVATED for event in snapshot.events
    )
    assert any(item.code == DiagnosticCode.READ_FAILED for item in diagnostics)


def test_parser_with_malformed_frontmatter_preserves_missing_metadata(
    tmp_path: Path,
) -> None:
    spool = write_spool(
        tmp_path,
        [
            hook(
                "read_succeeded",
                tool_id="activation-1",
                path="/skills/testing/SKILL.md",
                snapshot=payload("not frontmatter"),
            )
        ],
    )

    snapshot, diagnostics = build_conversation_snapshot(
        "conversation-1",
        None,
        spool,
    )

    activation = next(
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATED
    )
    assert "skill_name" not in activation.payload
    assert any(item.code == DiagnosticCode.FRONTMATTER_INVALID for item in diagnostics)


def test_parser_with_unavailable_resource_preserves_path_and_reason(
    tmp_path: Path,
) -> None:
    spool = write_spool(
        tmp_path,
        [
            hook(
                "read_succeeded",
                tool_id="activation-1",
                path="/skills/testing/SKILL.md",
                snapshot=payload("---\nname: testing\n---\n"),
            ),
            hook(
                "read_succeeded",
                tool_id="resource-1",
                path="/skills/testing/reference.md",
                snapshot={
                    "status": "unavailable",
                    "reason": "PermissionError",
                },
            ),
        ],
    )

    snapshot, diagnostics = build_conversation_snapshot(
        "conversation-1",
        None,
        spool,
    )

    resource = next(
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_RESOURCE_READ
    )
    assert resource.payload["path"] == "/skills/testing/reference.md"
    assert resource.payload["payload_snapshot"]["status"] == "unavailable"
    assert (
        resource.payload["payload_snapshot"]["unavailable_reason"] == "PermissionError"
    )
    assert any(item.code == DiagnosticCode.PAYLOAD_UNAVAILABLE for item in diagnostics)


def test_parser_with_truncated_transcript_returns_stable_diagnostic(
    tmp_path: Path,
) -> None:
    transcript_dir = tmp_path / "conversation-1"
    transcript_dir.mkdir()
    (transcript_dir / "conversation-1.jsonl").write_text(
        '{"role": "user", "content": "valid"}\n{"role":',
        encoding="utf-8",
    )

    _, diagnostics = build_conversation_snapshot(
        "conversation-1",
        transcript_dir,
        None,
    )

    assert any(item.code == DiagnosticCode.TRANSCRIPT_TRUNCATED for item in diagnostics)


def test_parser_with_nested_cursor_message_records_extracts_task(
    tmp_path: Path,
) -> None:
    transcript_dir = tmp_path / "conversation-1"
    transcript_dir.mkdir()
    (transcript_dir / "conversation-1.jsonl").write_text(
        json.dumps(
            {
                "role": "user",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<user_query>Build the dashboard</user_query>",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot, _ = build_conversation_snapshot(
        "conversation-1",
        transcript_dir,
        None,
    )

    tasks = [
        event
        for event in snapshot.events
        if event.event_type == EventType.TASK_RECORDED
    ]
    assert [event.payload["raw_text"] for event in tasks] == ["Build the dashboard"]


def test_parser_maps_textless_task_hooks_to_transcript_turns_by_order(
    tmp_path: Path,
) -> None:
    transcript_dir = tmp_path / "conversation-1"
    transcript_dir.mkdir()
    (transcript_dir / "conversation-1.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "role": "user",
                    "message": {
                        "content": [{"type": "text", "text": f"Prompt {index}"}]
                    },
                }
            )
            for index in (1, 2)
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = payload("---\nname: testing\n---\n")
    records = []
    for index in (1, 2):
        read = hook(
            "read_succeeded",
            tool_id=f"activation-{index}",
            path="/skills/testing/SKILL.md",
            snapshot=manifest,
        )
        read["payload"]["generation_id"] = f"generation-{index}"
        records.extend(
            [
                {
                    "schema_version": 1,
                    "captured_at": f"2026-09-19T12:0{index}:00+00:00",
                    "event_kind": "task_submitted",
                    "payload": {
                        "conversation_id": "conversation-1",
                        "generation_id": f"generation-{index}",
                    },
                },
                read,
            ]
        )
    spool = write_spool(tmp_path, records)

    snapshot, _ = build_conversation_snapshot(
        "conversation-1",
        transcript_dir,
        spool,
    )

    activations = [
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATED
    ]
    assert [event.turn_index for event in activations] == [0, 1]


def test_plugin_uses_collector_default_spool_filename(tmp_path: Path) -> None:
    manifest = payload("---\nname: testing\n---\n")
    spool = tmp_path / "cursor-hook-spool.jsonl"
    spool.write_text(
        "".join(
            f"{json.dumps(record)}\n"
            for record in [
                hook(
                    "read_succeeded",
                    tool_id="activation-1",
                    path="/skills/testing/SKILL.md",
                    snapshot=manifest,
                ),
                {
                    "schema_version": 1,
                    "captured_at": "2026-09-19T12:00:01+00:00",
                    "event_kind": "session_ended",
                    "payload": {"conversation_id": "conversation-1"},
                },
            ]
        ),
        encoding="utf-8",
    )
    context = DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=tmp_path / "missing",
        grace_seconds=300,
    )

    references = list(CursorPlugin().discover(context))

    assert [ref.native_conversation_id for ref in references] == ["conversation-1"]
    snapshot = CursorPlugin().snapshot(references[0], context=context)
    assert any(
        event.event_type == EventType.SKILL_ACTIVATED for event in snapshot.events
    )


def test_plugin_ignores_newer_hook_records_from_other_conversations(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "conversation-1.jsonl"
    transcript.write_text(
        '{"role":"user","message":{"content":[{"type":"text","text":"Done"}]}}\n',
        encoding="utf-8",
    )
    spool = write_spool(
        tmp_path,
        [
            {
                "schema_version": 1,
                "captured_at": "2026-09-19T12:00:00+00:00",
                "event_kind": "task_submitted",
                "payload": {"conversation_id": "conversation-1"},
            },
            {
                "schema_version": 1,
                "captured_at": "2026-09-19T12:09:00+00:00",
                "event_kind": "task_submitted",
                "payload": {"conversation_id": "conversation-2"},
            },
        ],
    )
    transcript_time = datetime(2026, 9, 19, 12, 0, tzinfo=UTC).timestamp()
    spool_time = datetime(2026, 9, 19, 12, 9, tzinfo=UTC).timestamp()
    os.utime(transcript, (transcript_time, transcript_time))
    os.utime(spool, (spool_time, spool_time))
    context = DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=transcript,
        spool_override=spool,
        grace_seconds=300,
    )
    reference = ConversationRef(
        harness_id="cursor",
        native_conversation_id="conversation-1",
        source_locators=(transcript, spool),
        extra={"transcript_dir": str(transcript)},
    )

    result = CursorPlugin().inspect(
        reference,
        now=datetime(2026, 9, 19, 12, 10, tzinfo=UTC),
        context=context,
    )

    assert result.verdict == EligibilityVerdict.READY


def test_plugin_discovery_excludes_subagent_transcripts(tmp_path: Path) -> None:
    conversation = tmp_path / "project" / "agent-transcripts" / "conversation-1"
    subagents = conversation / "subagents"
    subagents.mkdir(parents=True)
    (conversation / "conversation-1.jsonl").write_text("{}\n", encoding="utf-8")
    (subagents / "child-agent.jsonl").write_text("{}\n", encoding="utf-8")
    context = DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=tmp_path,
        spool_override=tmp_path / "missing-spool.jsonl",
        grace_seconds=0,
    )

    references = list(CursorPlugin().discover(context))

    assert [ref.native_conversation_id for ref in references] == ["conversation-1"]


def test_plugin_with_active_spool_only_source_defers_ingest(tmp_path: Path) -> None:
    spool = write_spool(
        tmp_path,
        [
            {
                "schema_version": 1,
                "captured_at": "2026-09-19T12:00:00+00:00",
                "event_kind": "session_started",
                "payload": {"conversation_id": "conversation-1"},
            }
        ],
    )
    context = DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=tmp_path / "missing",
        spool_override=spool,
        grace_seconds=300,
    )
    reference = ConversationRef(
        harness_id="cursor",
        native_conversation_id="conversation-1",
        extra={"spool_only": True},
    )

    result = CursorPlugin().inspect(
        reference,
        now=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
        context=context,
    )

    assert result.verdict == EligibilityVerdict.DEFER
