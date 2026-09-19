"""Tests for the Cursor hook collector."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from skillscope.plugins.cursor.collector import (
    VALID_EVENT_KINDS,
    _sanitise_payload,
    build_record,
    snapshot_skill_manifest,
    append_to_spool,
)


class TestSnapshotSkillManifest(unittest.TestCase):
    def test_captures_body_on_success(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "SKILL.md"
            path.write_text("---\nname: probe\n---\n", encoding="utf-8")
            snap = snapshot_skill_manifest(
                "read_succeeded",
                {"tool_input": {"file_path": str(path)}},
            )
        self.assertIsNotNone(snap)
        self.assertEqual(snap["status"], "captured")
        self.assertEqual(snap["content"], "---\nname: probe\n---\n")
        self.assertEqual(snap["byte_length"], 20)
        self.assertIn("sha256", snap)

    def test_not_triggered_on_failure(self):
        snap = snapshot_skill_manifest(
            "read_failed",
            {"tool_input": {"file_path": "/tmp/SKILL.md"}},
        )
        self.assertIsNone(snap)

    def test_rejects_non_skill_filenames(self):
        for name in ("SKILLS.md", "skill.md", "SKILL.mdx", "reference.md"):
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / name
                path.write_text("x", encoding="utf-8")
                snap = snapshot_skill_manifest(
                    "read_succeeded",
                    {"tool_input": {"file_path": str(path)}},
                )
                self.assertIsNone(snap, f"Should reject {name}")

    def test_rejects_glob_paths(self):
        for p in ("**/SKILL.md", "/tmp/*/SKILL.md", "/tmp/[a]/SKILL.md"):
            snap = snapshot_skill_manifest(
                "read_succeeded",
                {"tool_input": {"file_path": p}},
            )
            self.assertIsNone(snap, f"Should reject glob: {p}")

    def test_unavailable_when_file_missing(self):
        snap = snapshot_skill_manifest(
            "read_succeeded",
            {"tool_input": {"file_path": "/nonexistent/SKILL.md"}},
        )
        self.assertIsNotNone(snap)
        self.assertEqual(snap["status"], "unavailable")
        self.assertIn("reason", snap)

    def test_unavailable_when_non_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "SKILL.md"
            path.write_bytes(b"\x80\x81\x82")
            snap = snapshot_skill_manifest(
                "read_succeeded",
                {"tool_input": {"file_path": str(path)}},
            )
        self.assertIsNotNone(snap)
        self.assertEqual(snap["status"], "unavailable")

    def test_no_tool_input(self):
        snap = snapshot_skill_manifest("read_succeeded", {})
        self.assertIsNone(snap)

    def test_legacy_path_key(self):
        """Accepts tool_input.path as fallback."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "SKILL.md"
            path.write_text("---\nname: x\n---\n", encoding="utf-8")
            snap = snapshot_skill_manifest(
                "read_succeeded",
                {"tool_input": {"path": str(path)}},
            )
        self.assertIsNotNone(snap)
        self.assertEqual(snap["status"], "captured")


class TestSanitisePayload(unittest.TestCase):
    def test_drops_sensitive_fields(self):
        raw = {
            "conversation_id": "c1",
            "user_email": "secret@example.com",
            "model": "gpt-x",
            "tool_output": "big blob",
            "tool_name": "Read",
            "tool_input": {"file_path": "/a"},
            "generation_id": "g1",
        }
        clean = _sanitise_payload(raw)
        self.assertNotIn("user_email", clean)
        self.assertNotIn("model", clean)
        self.assertNotIn("tool_output", clean)
        self.assertIn("conversation_id", clean)
        self.assertIn("tool_name", clean)

    def test_retains_failure_fields(self):
        raw = {
            "conversation_id": "c1",
            "failure_type": "error",
            "error_message": "not found",
            "is_interrupt": False,
        }
        clean = _sanitise_payload(raw)
        self.assertEqual(clean["failure_type"], "error")
        self.assertEqual(clean["error_message"], "not found")


class TestBuildRecord(unittest.TestCase):
    def test_schema_version_and_event_kind(self):
        rec = build_record("session_started", {"conversation_id": "c1"})
        self.assertEqual(rec["schema_version"], 1)
        self.assertEqual(rec["event_kind"], "session_started")
        self.assertIn("captured_at", rec)
        self.assertIn("payload", rec)

    def test_no_snapshot_for_non_read(self):
        rec = build_record("session_ended", {"conversation_id": "c1"})
        self.assertIsNone(rec["skill_manifest_snapshot"])


class TestAppendToSpool(unittest.TestCase):
    def test_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            spool = Path(d) / "sub" / "spool.jsonl"
            rec1 = build_record("session_started", {"conversation_id": "c1"})
            rec2 = build_record("session_ended", {"conversation_id": "c1"})
            append_to_spool(rec1, spool)
            append_to_spool(rec2, spool)
            lines = spool.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["event_kind"], "session_started")
        self.assertEqual(json.loads(lines[1])["event_kind"], "session_ended")


class TestValidEventKinds(unittest.TestCase):
    def test_expected_kinds(self):
        self.assertEqual(
            VALID_EVENT_KINDS,
            {
                "session_started",
                "task_submitted",
                "read_succeeded",
                "read_failed",
                "session_ended",
            },
        )


if __name__ == "__main__":
    unittest.main()
