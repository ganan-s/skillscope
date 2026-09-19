"""Conformance tests for the harness ingestion contract.

Covers all ten cases from docs/03-ingestion-contract.md, exercised through
the Cursor adapter as the v1 reference implementation.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from skillscope.domain.models import (
    DiagnosticCode,
    EventType,
    EvidenceQuality,
)
from skillscope.plugins.cursor.parser import (
    build_conversation_snapshot,
    infer_source_bucket,
    parse_frontmatter,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cursor"


def _spool_line(event_kind, conversation_id="conv-c", **payload_overrides):
    """Build a single spool JSONL line."""
    payload = {"conversation_id": conversation_id, **payload_overrides}
    rec = {
        "schema_version": 1,
        "captured_at": "2026-09-19T12:00:00+00:00",
        "event_kind": event_kind,
        "payload": payload,
        "skill_manifest_snapshot": None,
    }
    return rec


def _write_spool(tmp, records):
    spool = Path(tmp) / "spool.jsonl"
    with spool.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return spool


def _skill_read_success(
    conv_id="conv-c",
    tool_use_id="tu-1",
    path="/s/SKILL.md",
    content="---\nname: test\n---\n",
):
    """Build a confirmed-success spool record with manifest snapshot."""
    return {
        "schema_version": 1,
        "captured_at": "2026-09-19T12:00:00+00:00",
        "event_kind": "read_succeeded",
        "payload": {
            "conversation_id": conv_id,
            "generation_id": "gen-1",
            "tool_use_id": tool_use_id,
            "tool_name": "Read",
            "tool_input": {"file_path": path},
            "cursor_version": "3.21.13",
        },
        "skill_manifest_snapshot": {
            "status": "captured",
            "path": path,
            "sha256": "abcd1234",
            "byte_length": len(content.encode()),
            "content": content,
        },
    }


def _skill_read_failure(conv_id="conv-c", tool_use_id="tu-fail", path="/s/SKILL.md"):
    return {
        "schema_version": 1,
        "captured_at": "2026-09-19T12:00:00+00:00",
        "event_kind": "read_failed",
        "payload": {
            "conversation_id": conv_id,
            "generation_id": "gen-1",
            "tool_use_id": tool_use_id,
            "tool_name": "Read",
            "tool_input": {"file_path": path},
            "failure_type": "error",
            "error_message": "File not found",
            "is_interrupt": False,
        },
        "skill_manifest_snapshot": None,
    }


class TestContractConformance(unittest.TestCase):
    """All ten cases from docs/03-ingestion-contract.md section 'Conformance tests'."""

    def test_1_confirmed_success_produces_activation(self):
        """Case 1: A confirmed exact SKILL.md read produces one activation."""
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [_skill_read_success()])
            snap, _ = build_conversation_snapshot("conv-c", None, spool)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 1)
        self.assertEqual(activations[0].evidence.quality, EvidenceQuality.CONFIRMED)

    def test_2_repeated_activation_produces_second_event(self):
        """Case 2: A repeated confirmed activation produces a second, stable event."""
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(
                tmp,
                [
                    _skill_read_success(tool_use_id="tu-1"),
                    _skill_read_success(tool_use_id="tu-2"),
                ],
            )
            snap, _ = build_conversation_snapshot("conv-c", None, spool)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 2)
        self.assertNotEqual(activations[0].event_id, activations[1].event_id)

    def test_3_failure_produces_no_activation(self):
        """Case 3: An unsuccessful outcome produces no activation."""
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [_skill_read_failure()])
            snap, diags = build_conversation_snapshot("conv-c", None, spool)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 0)
        fail_diags = [d for d in diags if d.code == DiagnosticCode.READ_FAILED]
        self.assertEqual(len(fail_diags), 1)

    def test_4_negative_cases_produce_no_activation(self):
        """Case 4: Non-manifest operations produce no activation."""
        negative_paths = [
            "/s/SKILLS.md",
            "/s/skill.md",
            "/s/SKILL.mdx",
            "/s/**/SKILL.md",
            "/s/reference.md",
        ]
        for bad_path in negative_paths:
            with tempfile.TemporaryDirectory() as tmp:
                rec = _skill_read_success(path=bad_path)
                # Collector rejects non-SKILL.md basenames and globs
                if Path(bad_path).name != "SKILL.md" or any(
                    c in bad_path for c in "*?["
                ):
                    rec["skill_manifest_snapshot"] = None
                spool = _write_spool(tmp, [rec])
                snap, _ = build_conversation_snapshot("conv-c", None, spool)

            activations = [
                e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
            ]
            self.assertEqual(len(activations), 0, f"Should reject {bad_path}")

    def test_5_missing_payload_preserves_path(self):
        """Case 5: Missing payload preserves path and marks status unavailable."""
        rec = _skill_read_success()
        rec["skill_manifest_snapshot"]["status"] = "unavailable"
        rec["skill_manifest_snapshot"]["reason"] = "OSError"
        rec["skill_manifest_snapshot"]["content"] = None
        rec["skill_manifest_snapshot"]["sha256"] = None
        rec["skill_manifest_snapshot"]["byte_length"] = None

        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [rec])
            snap, diags = build_conversation_snapshot("conv-c", None, spool)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 1)
        self.assertEqual(activations[0].payload["path"], "/s/SKILL.md")
        self.assertEqual(
            activations[0].payload["payload_snapshot"]["status"], "unavailable"
        )
        unavail_diags = [
            d for d in diags if d.code == DiagnosticCode.PAYLOAD_UNAVAILABLE
        ]
        self.assertEqual(len(unavail_diags), 1)

    def test_6_malformed_frontmatter_no_invented_name(self):
        """Case 6: Malformed frontmatter does not invent name or description."""
        rec = _skill_read_success(content="no frontmatter here")
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [rec])
            snap, diags = build_conversation_snapshot("conv-c", None, spool)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 1)
        self.assertNotIn("skill_name", activations[0].payload)
        fm_diags = [d for d in diags if d.code == DiagnosticCode.FRONTMATTER_INVALID]
        self.assertEqual(len(fm_diags), 1)

    def test_7_zero_activation_still_produces_snapshot(self):
        """Case 7: A zero-activation ready conversation still produces a snapshot."""
        with tempfile.TemporaryDirectory() as tmp:
            # Session with no reads at all
            spool = _write_spool(
                tmp,
                [
                    _spool_line("session_started"),
                    _spool_line("session_ended"),
                ],
            )
            snap, _ = build_conversation_snapshot("conv-c", None, spool)

        self.assertIsNotNone(snap)
        self.assertEqual(snap.native_conversation_id, "conv-c")
        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 0)

    def test_8_deterministic_replay(self):
        """Case 8: Parsing the same source revision is deterministic."""
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [_skill_read_success()])
            ts = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
            snap1, _ = build_conversation_snapshot(
                "conv-c", None, spool, source_updated_at=ts
            )
            snap2, _ = build_conversation_snapshot(
                "conv-c", None, spool, source_updated_at=ts
            )

        self.assertEqual(
            snap1.source_revision.revision,
            snap2.source_revision.revision,
        )
        self.assertEqual(len(snap1.events), len(snap2.events))
        for e1, e2 in zip(snap1.events, snap2.events, strict=True):
            self.assertEqual(e1.event_id, e2.event_id)

    def test_9_continuation_produces_replacement(self):
        """Case 9: Continuing a conversation produces a replacement snapshot."""
        with tempfile.TemporaryDirectory() as tmp:
            ts1 = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
            spool1 = _write_spool(tmp, [_skill_read_success(tool_use_id="tu-1")])
            snap1, _ = build_conversation_snapshot(
                "conv-c", None, spool1, source_updated_at=ts1
            )

        with tempfile.TemporaryDirectory() as tmp:
            ts2 = datetime(2026, 9, 19, 13, 0, 0, tzinfo=UTC)
            spool2 = _write_spool(
                tmp,
                [
                    _skill_read_success(tool_use_id="tu-1"),
                    _skill_read_success(tool_use_id="tu-3"),
                ],
            )
            snap2, _ = build_conversation_snapshot(
                "conv-c", None, spool2, source_updated_at=ts2
            )

        # Snap2 has more events, different revision
        self.assertNotEqual(
            snap1.source_revision.revision, snap2.source_revision.revision
        )
        acts1 = [e for e in snap1.events if e.event_type == EventType.SKILL_ACTIVATED]
        acts2 = [e for e in snap2.events if e.event_type == EventType.SKILL_ACTIVATED]
        self.assertEqual(len(acts1), 1)
        self.assertEqual(len(acts2), 2)
        # The original activation's event_id is stable
        self.assertEqual(acts1[0].event_id, "tu-1")
        self.assertIn("tu-1", [a.event_id for a in acts2])

    def test_10_no_cursor_shape_leaks(self):
        """Case 10: No native Cursor shape leaks into canonical DTOs."""
        with tempfile.TemporaryDirectory() as tmp:
            spool = _write_spool(tmp, [_skill_read_success()])
            snap, _ = build_conversation_snapshot("conv-c", None, spool)

        d = snap.to_dict()
        raw = json.dumps(d)
        # These Cursor-native fields must not appear in the canonical output
        for cursor_field in (
            "user_email",
            "model",
            "hook_event_name",
            "transcript_path",
            "tool_output",
        ):
            self.assertNotIn(f'"{cursor_field}"', raw)


class TestOfflineReadIsNotActivation(unittest.TestCase):
    """Offline transcript reads must never become activations."""

    def test_offline_read_produces_diagnostic_not_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript_dir = Path(tmp) / "conv-offline"
            transcript_dir.mkdir()
            (transcript_dir / "conv-offline.jsonl").write_text(
                '{"role": "assistant", "content": [{"type": "tool_use", "id": "tu-x", '
                '"name": "Read", "input": {"path": "/skills/SKILL.md"}}]}\n'
                '{"type": "turn_ended", "status": "success"}\n'
            )
            snap, diags = build_conversation_snapshot(
                "conv-offline", transcript_dir, None
            )

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 0)
        unknown_diags = [
            d for d in diags if d.code == DiagnosticCode.READ_OUTCOME_UNKNOWN
        ]
        self.assertEqual(len(unknown_diags), 1)


class TestFrontmatter(unittest.TestCase):
    def test_valid_frontmatter(self):
        fm = parse_frontmatter("---\nname: auth\ndescription: Auth skill\n---\nbody")
        self.assertIsNotNone(fm)
        self.assertEqual(fm["name"], "auth")
        self.assertEqual(fm["description"], "Auth skill")

    def test_missing_name(self):
        fm = parse_frontmatter("---\ndescription: only desc\n---\n")
        self.assertIsNone(fm)

    def test_no_frontmatter(self):
        fm = parse_frontmatter("just text")
        self.assertIsNone(fm)

    def test_empty_frontmatter(self):
        fm = parse_frontmatter("---\n---\n")
        self.assertIsNone(fm)


class TestSourceBucketInference(unittest.TestCase):
    def test_cursor_builtin(self):
        from skillscope.domain.models import SourceBucket

        self.assertEqual(
            infer_source_bucket("/home/u/.cursor/skills-cursor/auth/SKILL.md"),
            SourceBucket.CURSOR_BUILTIN,
        )

    def test_user_claude_plugin(self):
        from skillscope.domain.models import SourceBucket

        self.assertEqual(
            infer_source_bucket("/home/u/.claude/plugins/cache/x/SKILL.md"),
            SourceBucket.USER,
        )

    def test_project_skill(self):
        from skillscope.domain.models import SourceBucket

        self.assertEqual(
            infer_source_bucket(
                "/home/u/project/skills/SKILL.md",
                workspace_roots=["/home/u/project"],
            ),
            SourceBucket.PROJECT,
        )

    def test_unknown(self):
        from skillscope.domain.models import SourceBucket

        self.assertEqual(
            infer_source_bucket("/weird/path/SKILL.md"),
            SourceBucket.UNKNOWN,
        )


if __name__ == "__main__":
    unittest.main()
