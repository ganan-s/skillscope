"""Tests for the Cursor harness plugin (discovery, inspect, snapshot)."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from skillscope.domain.models import (
    EligibilityVerdict,
    EventType,
    ReadinessBasis,
)
from skillscope.plugins.base import ConversationRef, DiscoveryContext
from skillscope.plugins.cursor.plugin import CursorPlugin

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cursor"


def _make_context(tmp, transcript_override=None, spool_override=None, grace_seconds=0):
    return DiscoveryContext(
        home=Path(tmp),
        user_data=Path(tmp),
        transcript_override=transcript_override,
        spool_override=spool_override,
        grace_seconds=grace_seconds,
    )


class TestCursorPluginProtocol(unittest.TestCase):
    def test_has_id(self):
        self.assertEqual(CursorPlugin().id, "cursor")

    def test_detects_platform(self):
        p = CursorPlugin().detect_platform()
        self.assertEqual(p.harness, "cursor")


class TestDiscovery(unittest.TestCase):
    def test_discovers_from_transcript_fixtures(self):
        plugin = CursorPlugin()
        ctx = _make_context(
            "/tmp",
            transcript_override=FIXTURES / "transcripts",
            spool_override=FIXTURES / "hooks.jsonl",
        )
        refs = list(plugin.discover(ctx))
        conv_ids = {r.native_conversation_id for r in refs}
        self.assertIn("conv-test-1", conv_ids)

    def test_discovers_from_spool_only(self):
        plugin = CursorPlugin()
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool.jsonl"
            spool.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "event_kind": "session_started",
                        "payload": {"conversation_id": "spool-only-conv"},
                    }
                )
                + "\n"
            )
            ctx = _make_context(
                tmp,
                transcript_override=Path(tmp) / "empty",
                spool_override=spool,
            )
            refs = list(plugin.discover(ctx))

        conv_ids = {r.native_conversation_id for r in refs}
        self.assertIn("spool-only-conv", conv_ids)


class TestInspect(unittest.TestCase):
    def test_ready_with_session_end(self):
        plugin = CursorPlugin()
        ctx = _make_context(
            "/tmp",
            transcript_override=FIXTURES / "transcripts",
            spool_override=FIXTURES / "hooks.jsonl",
        )
        ref = ConversationRef(
            harness_id="cursor",
            native_conversation_id="conv-test-1",
            source_locators=(FIXTURES / "transcripts" / "conv-test-1",),
            extra={"transcript_dir": str(FIXTURES / "transcripts" / "conv-test-1")},
        )
        now = datetime(2026, 9, 20, 0, 0, 0, tzinfo=UTC)
        elig = plugin.inspect(ref, now=now, context=ctx)
        self.assertEqual(elig.verdict, EligibilityVerdict.READY)
        self.assertEqual(elig.basis, ReadinessBasis.NATIVE_END)

    def test_quiescent_with_grace(self):
        plugin = CursorPlugin()
        with tempfile.TemporaryDirectory() as tmp:
            no_end_spool = Path(tmp) / "spool.jsonl"
            no_end_spool.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "event_kind": "session_started",
                        "payload": {"conversation_id": "conv-test-1"},
                    }
                )
                + "\n"
            )
            ctx = _make_context(
                tmp,
                transcript_override=FIXTURES / "transcripts",
                spool_override=no_end_spool,
                grace_seconds=0,
            )
            ref = ConversationRef(
                harness_id="cursor",
                native_conversation_id="conv-test-1",
                source_locators=(),
                extra={"transcript_dir": str(FIXTURES / "transcripts" / "conv-test-1")},
            )
            now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
            elig = plugin.inspect(ref, now=now, context=ctx)
        self.assertEqual(elig.verdict, EligibilityVerdict.READY)
        self.assertEqual(elig.basis, ReadinessBasis.QUIESCENT)

    def test_defer_spool_only_no_end(self):
        plugin = CursorPlugin()
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool.jsonl"
            spool.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "event_kind": "session_started",
                        "payload": {"conversation_id": "x"},
                    }
                )
                + "\n"
            )
            ctx = _make_context(tmp, spool_override=spool)
            ref = ConversationRef(
                harness_id="cursor",
                native_conversation_id="x",
                source_locators=(),
                extra={"spool_only": True},
            )
            now = datetime.now(UTC)
            elig = plugin.inspect(ref, now=now, context=ctx)
        self.assertEqual(elig.verdict, EligibilityVerdict.DEFER)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_from_fixtures(self):
        plugin = CursorPlugin()
        ctx = _make_context(
            "/tmp",
            transcript_override=FIXTURES / "transcripts",
            spool_override=FIXTURES / "hooks.jsonl",
        )
        ref = ConversationRef(
            harness_id="cursor",
            native_conversation_id="conv-test-1",
            source_locators=(FIXTURES / "transcripts" / "conv-test-1",),
            extra={"transcript_dir": str(FIXTURES / "transcripts" / "conv-test-1")},
        )
        snap = plugin.snapshot(ref, context=ctx)

        self.assertEqual(snap.harness_id, "cursor")
        self.assertEqual(snap.native_conversation_id, "conv-test-1")

        tasks = [e for e in snap.events if e.event_type == EventType.TASK_RECORDED]
        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(tasks), 2)
        # Two successful reads of the same SKILL.md
        self.assertEqual(len(activations), 2)
        self.assertEqual(tasks[0].payload["raw_text"], "Add a login form")

    def test_zero_skills_snapshot(self):
        plugin = CursorPlugin()
        ctx = _make_context(
            "/tmp",
            transcript_override=FIXTURES / "transcripts",
            spool_override=FIXTURES / "hooks_no_skills.jsonl",
        )
        ref = ConversationRef(
            harness_id="cursor",
            native_conversation_id="conv-no-skills",
            source_locators=(FIXTURES / "transcripts" / "conv-no-skills",),
            extra={"transcript_dir": str(FIXTURES / "transcripts" / "conv-no-skills")},
        )
        snap = plugin.snapshot(ref, context=ctx)

        activations = [
            e for e in snap.events if e.event_type == EventType.SKILL_ACTIVATED
        ]
        self.assertEqual(len(activations), 0)
        tasks = [e for e in snap.events if e.event_type == EventType.TASK_RECORDED]
        self.assertEqual(len(tasks), 1)


if __name__ == "__main__":
    unittest.main()
