"""End-to-end CLI tests: ingest fixtures into SQLite and verify canonical output."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from skillscope.cli import main as cli_main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cursor"


class TestIngestCLI(unittest.TestCase):
    def _ingest(self, db_path, transcripts=None, spool=None, grace=0):
        args = [
            "ingest",
            "--harness",
            "cursor",
            "--db",
            str(db_path),
            "--grace-seconds",
            str(grace),
        ]
        if transcripts:
            args.extend(["--transcripts", str(transcripts)])
        if spool:
            args.extend(["--spool", str(spool)])
        return cli_main(args)

    def test_ingest_creates_db_and_persists_conversations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            rc = self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )
            self.assertEqual(rc, 0)

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row

            convs = conn.execute("SELECT * FROM conversations").fetchall()
            self.assertGreaterEqual(len(convs), 1)

            # conv-test-1 should be present
            conv_ids = [r["native_conversation_id"] for r in convs]
            self.assertIn("conv-test-1", conv_ids)

            conn.close()

    def test_skill_activations_are_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row

            activations = conn.execute(
                "SELECT * FROM events WHERE event_type = 'skill.activated'"
            ).fetchall()
            self.assertGreaterEqual(len(activations), 1)

            for act in activations:
                payload = json.loads(act["payload"])
                self.assertIn("path", payload)
                self.assertIn("source_bucket", payload)
                self.assertIn("payload_snapshot", payload)
                # No Cursor-native fields
                raw = json.dumps(payload)
                self.assertNotIn("user_email", raw)
                self.assertNotIn("tool_output", raw)

            conn.close()

    def test_tasks_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row

            tasks = conn.execute(
                "SELECT * FROM events WHERE event_type = 'task.recorded' "
                "AND native_conversation_id = 'conv-test-1' "
                "ORDER BY sequence"
            ).fetchall()
            self.assertGreaterEqual(len(tasks), 1)

            first_payload = json.loads(tasks[0]["payload"])
            self.assertIn("raw_text", first_payload)
            self.assertEqual(first_payload["raw_text"], "Add a login form")

            conn.close()

    def test_idempotent_reingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )
            # Second ingest should be idempotent
            rc = self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )
            self.assertEqual(rc, 0)

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            convs = conn.execute("SELECT * FROM conversations").fetchall()
            # Should still have same number, not duplicated
            conv_ids = [r["native_conversation_id"] for r in convs]
            self.assertEqual(conv_ids.count("conv-test-1"), 1)
            conn.close()

    def test_zero_skills_conversation_ingested(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks_no_skills.jsonl",
            )

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row

            convs = conn.execute(
                "SELECT * FROM conversations "
                "WHERE native_conversation_id = 'conv-no-skills'"
            ).fetchall()
            self.assertEqual(len(convs), 1)

            activations = conn.execute(
                "SELECT * FROM events WHERE event_type = 'skill.activated' "
                "AND native_conversation_id = 'conv-no-skills'"
            ).fetchall()
            self.assertEqual(len(activations), 0)

            conn.close()

    def test_failed_reads_are_diagnostics_not_activations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            self._ingest(
                db,
                transcripts=FIXTURES / "transcripts",
                spool=FIXTURES / "hooks.jsonl",
            )

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row

            diags = conn.execute(
                "SELECT * FROM diagnostics WHERE code = 'read_failed'"
            ).fetchall()
            self.assertGreaterEqual(len(diags), 1)

            conn.close()

    def test_no_command_prints_help(self):
        rc = cli_main([])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
