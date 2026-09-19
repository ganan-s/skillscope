from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from capture import snapshot_skill_manifest


class SnapshotSkillManifestTests(unittest.TestCase):
    def test_captures_skill_manifest_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text("---\nname: probe\n---\n", encoding="utf-8")

            snapshot = snapshot_skill_manifest(
                "read_succeeded",
                {"tool_input": {"file_path": str(path)}},
            )

        assert snapshot is not None
        self.assertEqual(snapshot["status"], "captured")
        self.assertEqual(snapshot["content"], "---\nname: probe\n---\n")
        self.assertEqual(snapshot["byte_length"], 20)

    def test_does_not_snapshot_failed_read(self) -> None:
        snapshot = snapshot_skill_manifest(
            "read_failed",
            {"tool_input": {"file_path": "/tmp/example/SKILL.md"}},
        )

        self.assertIsNone(snapshot)

    def test_rejects_non_manifest_and_glob_paths(self) -> None:
        for path in (
            "/tmp/example/reference.md",
            "/tmp/example/SKILLS.md",
            "/tmp/**/SKILL.md",
        ):
            with self.subTest(path=path):
                snapshot = snapshot_skill_manifest(
                    "read_succeeded",
                    {"tool_input": {"file_path": path}},
                )
                self.assertIsNone(snapshot)


if __name__ == "__main__":
    unittest.main()
