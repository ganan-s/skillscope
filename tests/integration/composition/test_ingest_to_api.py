from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from skillscope.bootstrap import build_api_app
from skillscope.cli import main

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "cursor"


def test_cursor_ingest_to_api_exposes_repeated_activations(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"

    exit_code = main(
        [
            "ingest",
            "--harness",
            "cursor",
            "--db",
            str(db_path),
            "--transcripts",
            str(FIXTURES / "transcripts"),
            "--spool",
            str(FIXTURES / "hooks.jsonl"),
            "--grace-seconds",
            "0",
        ]
    )
    client = TestClient(build_api_app(db_path))
    listing = client.get("/api/v1/conversations").json()
    item = next(
        entry for entry in listing["items"] if entry["title"] == "Add a login form"
    )
    detail = client.get(f"/api/v1/conversations/{item['id']}").json()

    assert exit_code == 0
    assert item["skills"] == [
        {
            "name": "auth",
            "path": "/home/user/.cursor/skills-cursor/auth/SKILL.md",
            "source": "cursor-builtin",
            "activation_count": 2,
        }
    ]
    assert [entry["id"] for entry in detail["skill_activations"]] == [
        "tu-success-1",
        "tu-success-2",
    ]
    assert item["load_failure_count"] == 1
    assert [entry["id"] for entry in detail["skill_load_failures"]] == ["tu-fail-1"]
    assert detail["skill_activations"][0]["observations"] == {
        "resource_follow_through": False,
        "repeated_in_conversation": True,
        "followed_by_user_task": True,
        "containing_turn_status": "success",
    }
