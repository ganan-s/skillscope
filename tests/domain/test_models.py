"""Tests for canonical domain models and their serialisation."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    Diagnostic,
    DiagnosticCode,
    Evidence,
    EvidenceQuality,
    EventType,
    IngestEligibility,
    EligibilityVerdict,
    PayloadSnapshot,
    PayloadStatus,
    ReadinessBasis,
    SourceBucket,
    SourceRevision,
    TimeProvenance,
)


def _make_evidence(**overrides):
    defaults = dict(
        source_kind="hook",
        native_event_kind="postToolUse",
        native_event_id="tu-1",
        quality=EvidenceQuality.CONFIRMED,
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def _make_event(*, seq=1, event_type=EventType.SKILL_ACTIVATED, **overrides):
    defaults = dict(
        contract_version=CONTRACT_VERSION,
        event_id=f"evt-{seq}",
        event_type=event_type,
        harness_id="cursor",
        native_conversation_id="conv-1",
        sequence=seq,
        evidence=_make_evidence(),
    )
    defaults.update(overrides)
    return CanonicalEvent(**defaults)


def _make_snapshot(events=(), diagnostics=()):
    return ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conv-1",
        source_revision=SourceRevision(
            revision="rev-abc",
            updated_at=datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc),
        ),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=tuple(events),
        diagnostics=tuple(diagnostics),
        title="Test conversation",
        workspace_paths=("/home/user/project",),
        started_at=datetime(2026, 9, 19, 11, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestCanonicalEventSerialization(unittest.TestCase):
    def test_round_trip_is_json_safe(self):
        event = _make_event(
            payload={"path": "/skills/SKILL.md", "source_bucket": "user"},
        )
        d = event.to_dict()
        raw = json.dumps(d, sort_keys=True)
        restored = json.loads(raw)
        self.assertEqual(restored["event_type"], "skill.activated")
        self.assertEqual(restored["harness_id"], "cursor")
        self.assertEqual(restored["evidence"]["quality"], "confirmed")
        self.assertEqual(restored["payload"]["path"], "/skills/SKILL.md")

    def test_deterministic_event_id(self):
        e1 = _make_event(seq=1)
        e2 = _make_event(seq=1)
        self.assertEqual(e1.event_id, e2.event_id)

    def test_events_preserve_order(self):
        events = [_make_event(seq=i) for i in range(1, 4)]
        sequences = [e.sequence for e in events]
        self.assertEqual(sequences, [1, 2, 3])


class TestConversationSnapshotSerialization(unittest.TestCase):
    def test_snapshot_to_dict_round_trip(self):
        activation = _make_event(
            seq=1,
            event_type=EventType.SKILL_ACTIVATED,
            payload={"path": "/s/SKILL.md", "source_bucket": "user"},
        )
        task = _make_event(
            seq=2,
            event_type=EventType.TASK_RECORDED,
            payload={"raw_text": "hello"},
        )
        diag = Diagnostic(
            code=DiagnosticCode.READ_OUTCOME_UNKNOWN,
            message="offline read with no result",
            path="/s/SKILL.md",
        )
        snap = _make_snapshot(events=[activation, task], diagnostics=[diag])
        d = snap.to_dict()
        raw = json.dumps(d, sort_keys=True)
        restored = json.loads(raw)

        self.assertEqual(restored["contract_version"], CONTRACT_VERSION)
        self.assertEqual(restored["harness_id"], "cursor")
        self.assertEqual(restored["readiness_basis"], "native_end")
        self.assertEqual(len(restored["events"]), 2)
        self.assertEqual(restored["events"][0]["event_type"], "skill.activated")
        self.assertEqual(restored["events"][1]["event_type"], "task.recorded")
        self.assertEqual(len(restored["diagnostics"]), 1)
        self.assertEqual(
            restored["diagnostics"][0]["code"], "read_outcome_unknown"
        )

    def test_empty_events_snapshot(self):
        snap = _make_snapshot()
        d = snap.to_dict()
        self.assertEqual(d["events"], [])

    def test_missing_optional_fields(self):
        snap = ConversationSnapshot(
            contract_version=CONTRACT_VERSION,
            harness_id="cursor",
            native_conversation_id="conv-2",
            source_revision=SourceRevision(
                revision="rev-x",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            readiness_basis=ReadinessBasis.QUIESCENT,
            events=(),
        )
        d = snap.to_dict()
        self.assertIsNone(d["title"])
        self.assertIsNone(d["started_at"])
        self.assertIsNone(d["ended_at"])
        self.assertEqual(d["workspace_paths"], [])


class TestEnumValues(unittest.TestCase):
    def test_event_types(self):
        self.assertEqual(EventType.SESSION_CLOSED.value, "session.closed")
        self.assertEqual(EventType.TASK_RECORDED.value, "task.recorded")
        self.assertEqual(EventType.SKILL_ACTIVATED.value, "skill.activated")

    def test_source_buckets(self):
        self.assertEqual(SourceBucket.CURSOR_BUILTIN.value, "cursor-builtin")
        self.assertEqual(SourceBucket.UNKNOWN.value, "unknown")

    def test_payload_status(self):
        ps = PayloadSnapshot(
            status=PayloadStatus.CAPTURED,
            content="---\nname: test\n---\n",
            sha256="abc123",
            byte_length=20,
        )
        self.assertEqual(ps.status.value, "captured")

    def test_eligibility_verdicts(self):
        ready = IngestEligibility(
            verdict=EligibilityVerdict.READY,
            basis=ReadinessBasis.NATIVE_END,
        )
        defer = IngestEligibility(
            verdict=EligibilityVerdict.DEFER,
            reason="still growing",
        )
        self.assertEqual(ready.verdict.value, "ready")
        self.assertEqual(defer.verdict.value, "defer")


if __name__ == "__main__":
    unittest.main()
