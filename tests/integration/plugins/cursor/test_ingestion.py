from __future__ import annotations

import hashlib
import json
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
    failures = [
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATION_FAILED
    ]
    assert [event.event_id for event in failures] == ["failed-1"]
    assert failures[0].payload["path"] == "/skills/testing/SKILL.md"
    assert failures[0].payload["reason"] == "failed"
    assert "error_message" not in failures[0].payload


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


def test_parser_with_message_content_blocks_records_user_tasks(
    tmp_path: Path,
) -> None:
    transcript_dir = tmp_path / "conversation-1"
    transcript_dir.mkdir()
    (transcript_dir / "conversation-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": "Explain the repository."}
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "tu-unknown",
                                    "name": "Read",
                                    "input": {"path": "/skills/testing/SKILL.md"},
                                }
                            ]
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot, diagnostics = build_conversation_snapshot(
        "conversation-1",
        transcript_dir,
        None,
    )

    tasks = [
        event
        for event in snapshot.events
        if event.event_type == EventType.TASK_RECORDED
    ]
    assert [event.payload["raw_text"] for event in tasks] == ["Explain the repository."]
    assert snapshot.title == "Explain the repository."
    assert any(item.code == DiagnosticCode.READ_OUTCOME_UNKNOWN for item in diagnostics)


def test_parser_with_hook_prompt_field_records_task(tmp_path: Path) -> None:
    spool = write_spool(
        tmp_path,
        [
            {
                "schema_version": 1,
                "captured_at": "2026-09-19T12:00:00+00:00",
                "event_kind": "task_submitted",
                "payload": {
                    "conversation_id": "conversation-1",
                    "generation_id": "generation-1",
                    "prompt": "Explain the repository.",
                    "workspace_roots": ["/repo"],
                },
            }
        ],
    )

    snapshot, _ = build_conversation_snapshot("conversation-1", None, spool)

    tasks = [
        event
        for event in snapshot.events
        if event.event_type == EventType.TASK_RECORDED
    ]
    assert [event.payload["raw_text"] for event in tasks] == ["Explain the repository."]
    assert snapshot.workspace_paths == ("/repo",)


def test_plugin_discover_skips_subagent_transcripts(tmp_path: Path) -> None:
    parent_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    sub_id = "11111111-2222-3333-4444-555555555555"
    parent_dir = tmp_path / "projects" / "proj" / "agent-transcripts" / parent_id
    parent_dir.mkdir(parents=True)
    (parent_dir / f"{parent_id}.jsonl").write_text(
        json.dumps(
            {
                "role": "user",
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sub_dir = parent_dir / "subagents"
    sub_dir.mkdir()
    (sub_dir / f"{sub_id}.jsonl").write_text(
        json.dumps(
            {
                "role": "user",
                "message": {"content": [{"type": "text", "text": "Subagent"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    context = DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=tmp_path / "projects",
        spool_override=tmp_path / "missing-spool.jsonl",
    )

    ids = {ref.native_conversation_id for ref in CursorPlugin().discover(context)}

    assert parent_id in ids
    assert sub_id not in ids


def test_parser_with_failed_resource_read_does_not_emit_activation_failure(
    tmp_path: Path,
) -> None:
    spool = write_spool(
        tmp_path,
        [
            hook(
                "read_failed",
                tool_id="failed-resource",
                path="/skills/testing/reference.md",
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
        event.event_type == EventType.SKILL_ACTIVATION_FAILED
        for event in snapshot.events
    )
    assert any(item.code == DiagnosticCode.READ_FAILED for item in diagnostics)


def test_parser_with_interrupted_skill_read_maps_canonical_reason(
    tmp_path: Path,
) -> None:
    record = hook(
        "read_failed",
        tool_id="failed-interrupt",
        path="/skills/testing/SKILL.md",
        snapshot=None,
    )
    record["payload"]["is_interrupt"] = True
    spool = write_spool(tmp_path, [record])

    snapshot, _ = build_conversation_snapshot("conversation-1", None, spool)

    failure = next(
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATION_FAILED
    )
    assert failure.payload["reason"] == "interrupted"


def test_parser_with_turn_ended_emits_turn_completed(tmp_path: Path) -> None:
    transcript_dir = tmp_path / "conversation-1"
    transcript_dir.mkdir()
    (transcript_dir / "conversation-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "message": {
                            "content": [
                                {"type": "text", "text": "Explain the repository."}
                            ]
                        },
                    }
                ),
                json.dumps({"type": "turn_ended", "status": "error"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot, _ = build_conversation_snapshot(
        "conversation-1",
        transcript_dir,
        None,
    )

    turns = [
        event
        for event in snapshot.events
        if event.event_type == EventType.TURN_COMPLETED
    ]
    assert len(turns) == 1
    assert turns[0].turn_index == 0
    assert turns[0].payload["status"] == "error"


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
