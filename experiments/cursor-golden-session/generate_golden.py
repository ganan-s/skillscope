#!/usr/bin/env python3
"""Sanitize a local Cursor capture into a stable golden ingest pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_SPOOL = EXPERIMENT_DIR / ".local" / "raw-spool.jsonl"
DEFAULT_OUTPUT = EXPERIMENT_DIR / ".local" / "golden"
PROBE_SKILL = EXPERIMENT_DIR / "fixtures" / "probe-skill" / "SKILL.md"

STABLE_CONVERSATION_ID = "conv-live-1"
STABLE_PROMPT = "Load the probe skill twice, then read a missing SKILL.md."
STABLE_SKILL_PATH = "/home/user/.cursor/skills-cursor/probe/SKILL.md"
STABLE_MISSING_PATH = "/home/user/project/missing/SKILL.md"
STABLE_WORKSPACE = "/home/user/project"
STABLE_HOME = "/home/user"
STABLE_TIME = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

REQUIRED_KINDS = {
    "session_started": 1,
    "task_submitted": 1,
    "read_succeeded": 2,
    "read_failed": 1,
    "session_ended": 1,
}


class GoldenGenerationError(Exception):
    """Raised when a local capture is incomplete or unreadable."""


def capture_help(spool_path: Path) -> str:
    return (
        f"raw spool not found: {spool_path}\n"
        "No Cursor session has been captured yet. generate_golden.py only "
        "sanitizes a capture; it does not talk to Cursor.\n"
        "\n"
        "  1. uv run python experiments/cursor-golden-session/generate_golden.py "
        "--install-hooks\n"
        "  2. Confirm the hooks in Cursor Settings > Hooks\n"
        "  3. Start a NEW project conversation (this chat will not emit "
        "sessionStart)\n"
        "  4. Prompt the agent to read "
        "experiments/cursor-golden-session/fixtures/probe-skill/SKILL.md twice, "
        "then experiments/cursor-golden-session/fixtures/missing/SKILL.md\n"
        "  5. End that conversation so sessionEnd fires\n"
        "  6. Re-run generate_golden.py"
    )


def install_hooks(*, hooks_path: Path | None = None) -> Path:
    """Copy the experiment hook config into the project .cursor directory."""
    source = EXPERIMENT_DIR / "hooks.example.json"
    destination = hooks_path or EXPERIMENT_DIR.parents[1] / ".cursor" / "hooks.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return destination


def load_spool(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise GoldenGenerationError(capture_help(path))
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise GoldenGenerationError(
                f"malformed spool JSONL at {path}:{line_number}: {error}"
            ) from error
        if isinstance(value, dict):
            records.append(value)
    if not records:
        raise GoldenGenerationError(f"raw spool is empty: {path}")
    return records


def _conversation_id(record: dict[str, Any]) -> str | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    value = payload.get("conversation_id")
    return value if isinstance(value, str) and value else None


def _captured_at(record: dict[str, Any]) -> datetime:
    raw = record.get("captured_at")
    if not isinstance(raw, str):
        return datetime.min.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def select_conversation(
    records: list[dict[str, Any]],
    conversation_id: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        native_id = _conversation_id(record)
        if native_id is None:
            continue
        grouped.setdefault(native_id, []).append(record)
    if conversation_id is not None:
        selected = grouped.get(conversation_id)
        if not selected:
            raise GoldenGenerationError(
                f"conversation {conversation_id!r} was not found in the spool."
            )
        return conversation_id, selected

    ended = [
        (native_id, group)
        for native_id, group in grouped.items()
        if any(record.get("event_kind") == "session_ended" for record in group)
    ]
    if not ended:
        raise GoldenGenerationError(
            "no captured conversation includes session_ended.\n"
            "End the Cursor conversation so sessionEnd fires, then regenerate."
        )
    ended.sort(key=lambda item: max(_captured_at(record) for record in item[1]))
    native_id, group = ended[-1]
    return native_id, group


def validate_required_kinds(records: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter(
        str(record.get("event_kind"))
        for record in records
        if isinstance(record.get("event_kind"), str)
    )
    missing = [
        f"  {kind}: need >={required}, found {counts.get(kind, 0)}"
        for kind, required in REQUIRED_KINDS.items()
        if counts.get(kind, 0) < required
    ]
    if missing:
        raise GoldenGenerationError(
            "captured conversation is missing required hook kinds:\n"
            + "\n".join(missing)
            + "\nStart a new conversation, submit a prompt, read the probe "
            "SKILL.md twice, read a missing SKILL.md, then end the session."
        )
    return counts


def find_transcript(
    conversation_id: str,
    transcripts: Path | None,
    *,
    home: Path | None = None,
) -> Path:
    if transcripts is not None:
        if transcripts.is_file():
            return transcripts
        if transcripts.is_dir():
            matches = sorted(transcripts.rglob(f"{conversation_id}.jsonl"))
            if matches:
                return matches[0]
            matches = sorted(transcripts.rglob("*.jsonl"))
            if len(matches) == 1:
                return matches[0]
        raise GoldenGenerationError(
            f"transcript for {conversation_id} not found under {transcripts}"
        )

    projects = (home or Path.home()) / ".cursor" / "projects"
    matches = sorted(
        projects.glob(f"**/agent-transcripts/{conversation_id}/{conversation_id}.jsonl")
    )
    if not matches:
        matches = sorted(
            projects.glob(f"**/agent-transcripts/{conversation_id}/*.jsonl")
        )
    if not matches:
        raise GoldenGenerationError(
            f"transcript for {conversation_id} not found under {projects}.\n"
            "Pass --transcripts pointing at the agent-transcripts file or parent."
        )
    return matches[-1]


def _probe_snapshot(path: str) -> dict[str, Any]:
    body = PROBE_SKILL.read_bytes()
    return {
        "status": "captured",
        "path": path,
        "sha256": hashlib.sha256(body).hexdigest(),
        "byte_length": len(body),
        "content": body.decode("utf-8"),
    }


def _rewrite_string(value: str, replacements: list[tuple[str, str]]) -> str:
    rewritten = value
    for source, target in replacements:
        rewritten = rewritten.replace(source, target)
    return EMAIL_RE.sub("<redacted>", rewritten)


def _rewrite(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        return _rewrite_string(value, replacements)
    if isinstance(value, list):
        return [_rewrite(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite(item, replacements) for key, item in value.items()}
    return value


def _path_from_payload(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path", tool_input.get("path"))
    return raw if isinstance(raw, str) and raw else None


def build_replacements(
    native_id: str,
    records: list[dict[str, Any]],
    *,
    home: Path | None = None,
) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    generations: list[str] = []
    success_ids: list[str] = []
    failed_ids: list[str] = []
    for record in records:
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        generation = payload.get("generation_id")
        if isinstance(generation, str) and generation and generation not in generations:
            generations.append(generation)
        path = _path_from_payload(payload)
        if record.get("event_kind") == "read_succeeded" and path:
            replacements.append((path, STABLE_SKILL_PATH))
        elif record.get("event_kind") == "read_failed" and path:
            replacements.append((path, STABLE_MISSING_PATH))
        tool_id = payload.get("tool_use_id")
        if not isinstance(tool_id, str) or not tool_id:
            continue
        if record.get("event_kind") == "read_succeeded" and tool_id not in success_ids:
            success_ids.append(tool_id)
        elif record.get("event_kind") == "read_failed" and tool_id not in failed_ids:
            failed_ids.append(tool_id)

    replacements.append((native_id, STABLE_CONVERSATION_ID))
    replacements.extend(
        (generation, f"gen-{index}")
        for index, generation in enumerate(generations, start=1)
    )
    replacements.extend(
        (tool_id, f"tu-success-{index}")
        for index, tool_id in enumerate(success_ids, start=1)
    )
    replacements.extend(
        (tool_id, f"tu-fail-{index}")
        for index, tool_id in enumerate(failed_ids, start=1)
    )
    home_path = str(home or Path.home())
    replacements.append((home_path, STABLE_HOME))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    return replacements


def sanitize_spool(
    records: list[dict[str, Any]],
    replacements: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        copy = json.loads(json.dumps(record))
        copy["captured_at"] = (STABLE_TIME + timedelta(seconds=5 * index)).isoformat()
        payload = copy.get("payload")
        if not isinstance(payload, dict):
            copy["payload"] = {}
            payload = copy["payload"]
        copy["payload"] = _rewrite(payload, replacements)
        copy["payload"]["conversation_id"] = STABLE_CONVERSATION_ID
        copy["payload"]["workspace_roots"] = [STABLE_WORKSPACE]
        if copy.get("event_kind") == "task_submitted":
            tool_input = copy["payload"].setdefault("tool_input", {})
            if isinstance(tool_input, dict):
                tool_input["input"] = STABLE_PROMPT
        if copy.get("event_kind") == "read_succeeded":
            tool_input = copy["payload"].setdefault("tool_input", {})
            if isinstance(tool_input, dict):
                tool_input["file_path"] = STABLE_SKILL_PATH
            snapshot = copy.get("skill_manifest_snapshot")
            if isinstance(snapshot, dict) and snapshot.get("status") == "captured":
                copy["skill_manifest_snapshot"] = _probe_snapshot(STABLE_SKILL_PATH)
            elif isinstance(snapshot, dict):
                snapshot["path"] = STABLE_SKILL_PATH
        elif copy.get("event_kind") == "read_failed":
            tool_input = copy["payload"].setdefault("tool_input", {})
            if isinstance(tool_input, dict):
                tool_input["file_path"] = STABLE_MISSING_PATH
        sanitized.append(copy)
    return sanitized


def _redact_transcript_node(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        if "<user_query>" in value or value.strip() == STABLE_PROMPT:
            return f"<user_query>\n{STABLE_PROMPT}\n</user_query>"
        return _rewrite_string(value, replacements)
    if isinstance(value, list):
        redacted = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                redacted.append({**item, "text": "..."})
            else:
                redacted.append(_redact_transcript_node(item, replacements))
        return redacted
    if isinstance(value, dict):
        result = {
            key: _redact_transcript_node(item, replacements)
            for key, item in value.items()
        }
        if result.get("role") == "user" and isinstance(result.get("content"), str):
            result["content"] = f"<user_query>\n{STABLE_PROMPT}\n</user_query>"
        return result
    return value


def sanitize_transcript(
    path: Path,
    replacements: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise GoldenGenerationError(
                f"malformed transcript JSONL at {path}:{line_number}: {error}"
            ) from error
        if isinstance(value, dict):
            records.append(_redact_transcript_node(value, replacements))
    if not records:
        raise GoldenGenerationError(f"transcript is empty: {path}")
    return records


def expected_facts(
    spool: list[dict[str, Any]],
    transcript: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    kinds = Counter(
        str(record.get("event_kind"))
        for record in spool
        if isinstance(record.get("event_kind"), str)
    )
    activation_ids = [
        record["payload"]["tool_use_id"]
        for record in spool
        if record.get("event_kind") == "read_succeeded"
        and isinstance(record.get("payload"), dict)
        and isinstance(record["payload"].get("tool_use_id"), str)
    ]
    turn_completed = sum(
        1 for record in (transcript or []) if record.get("type") == "turn_ended"
    )
    return {
        "conversation_id": STABLE_CONVERSATION_ID,
        "spool_event_kinds": dict(kinds),
        "canonical_event_types": {
            "task.recorded": kinds["task_submitted"],
            "skill.activated": kinds["read_succeeded"],
            "skill.activation_failed": kinds["read_failed"],
            "turn.completed": turn_completed,
            "session.closed": 1,
        },
        "diagnostic_codes": ["read_failed"],
        "activation_ids": activation_ids,
        "task_text": STABLE_PROMPT,
        "skill_path": STABLE_SKILL_PATH,
    }


def write_golden(
    output: Path,
    spool: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> Path:
    transcript_dir = output / "transcripts" / STABLE_CONVERSATION_ID
    transcript_dir.mkdir(parents=True, exist_ok=True)
    spool_path = output / "hooks.jsonl"
    transcript_path = transcript_dir / f"{STABLE_CONVERSATION_ID}.jsonl"
    expected_path = output / "expected.json"
    spool_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in spool),
        encoding="utf-8",
    )
    transcript_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript),
        encoding="utf-8",
    )
    expected_path.write_text(
        json.dumps(expected_facts(spool, transcript), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def generate_golden(
    *,
    spool_path: Path = DEFAULT_SPOOL,
    transcripts: Path | None = None,
    conversation_id: str | None = None,
    output: Path = DEFAULT_OUTPUT,
    home: Path | None = None,
) -> Path:
    raw_records = load_spool(spool_path)
    native_id, selected = select_conversation(raw_records, conversation_id)
    validate_required_kinds(selected)
    transcript_source = find_transcript(native_id, transcripts, home=home)
    replacements = build_replacements(native_id, selected, home=home)
    sanitized_spool = sanitize_spool(selected, replacements)
    sanitized_transcript = sanitize_transcript(transcript_source, replacements)
    if output.exists():
        for child in output.rglob("*"):
            if child.is_file():
                child.unlink()
    return write_golden(output, sanitized_spool, sanitized_transcript)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sanitize a local Cursor capture into .local/golden/.",
    )
    parser.add_argument(
        "--spool",
        type=Path,
        default=DEFAULT_SPOOL,
        help="Raw collector spool (default: .local/raw-spool.jsonl)",
    )
    parser.add_argument(
        "--transcripts",
        type=Path,
        default=None,
        help="Transcript file or parent directory (otherwise search ~/.cursor)",
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Native conversation id (default: latest with session_ended)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Golden output directory (default: .local/golden)",
    )
    parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="Copy hooks.example.json to .cursor/hooks.json and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.install_hooks:
        destination = install_hooks()
        print(f"Installed Cursor hooks at {destination}")
        print(
            "Confirm them in Cursor Settings > Hooks, then start a NEW "
            "conversation before generating."
        )
        return 0
    try:
        output = generate_golden(
            spool_path=args.spool,
            transcripts=args.transcripts,
            conversation_id=args.conversation_id,
            output=args.output,
        )
    except GoldenGenerationError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Wrote golden session pack to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
