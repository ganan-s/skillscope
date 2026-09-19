"""SQLite read adapters for API-facing application projections."""

from __future__ import annotations

import base64
import json
import sqlite3
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from skillscope.application.queries import (
    ConversationDetail,
    ConversationPage,
    ConversationSummary,
    IngestCounts,
    InvalidPaginationError,
    PageRequest,
    Payload,
    SkillActivation,
    SkillResourceRead,
    SkillSummary,
    StoreError,
    StoreIncompatibleError,
    StoreMetadata,
    StoreMissingError,
    Task,
)
from skillscope.domain.models import public_conversation_id
from skillscope.storage.connection import (
    SUPPORTED_SCHEMA_VERSION,
    connect_readonly,
    get_schema_version,
)

_SKILL_SOURCES = {"user", "cursor-builtin", "agents", "project", "unknown"}
_TIME_PROVENANCE = {"native", "collector_observed", "derived", "missing"}


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _source(value: object) -> str:
    return value if isinstance(value, str) and value in _SKILL_SOURCES else "unknown"


def _time_provenance(value: object) -> str:
    return value if isinstance(value, str) and value in _TIME_PROVENANCE else "missing"


def _public_id(row: sqlite3.Row) -> str:
    return row["public_id"] or public_conversation_id(
        row["harness_id"],
        row["native_conversation_id"],
    )


def _encode_cursor(public_id: str) -> str:
    return base64.urlsafe_b64encode(public_id.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> str:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = base64.urlsafe_b64decode(cursor + padding).decode()
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidPaginationError("invalid cursor") from exc
    if not value:
        raise InvalidPaginationError("invalid cursor")
    return value


def _payload(value: Any) -> Payload:
    raw = value if isinstance(value, dict) else {}
    status = str(raw.get("status", "unavailable"))
    if status == "captured":
        return Payload(
            status=status,
            content=raw.get("content"),
            sha256=raw.get("sha256"),
            byte_length=raw.get("byte_length"),
            unavailable_reason=None,
        )
    return Payload(
        status="unavailable",
        content=None,
        sha256=None,
        byte_length=raw.get("byte_length"),
        unavailable_reason=raw.get("unavailable_reason") or "not_captured",
    )


class SQLiteReadRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        if not self._db_path.is_file():
            raise StoreMissingError(str(self._db_path))
        try:
            conn = connect_readonly(self._db_path)
            version = get_schema_version(conn)
        except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            raise StoreError("store cannot be read") from exc
        if version != SUPPORTED_SCHEMA_VERSION:
            conn.close()
            raise StoreIncompatibleError(str(version))
        return conn

    def list_conversations(self, request: PageRequest) -> ConversationPage:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM conversations "
                "ORDER BY ended_at IS NULL, ended_at DESC, "
                "started_at IS NULL, started_at DESC, public_id"
            ).fetchall()
            summaries = [self._summary(conn, row) for row in rows]
        except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            raise StoreError("store cannot be read") from exc
        finally:
            conn.close()

        start = 0
        if request.cursor is not None:
            public_id = _decode_cursor(request.cursor)
            try:
                start = next(
                    index + 1
                    for index, item in enumerate(summaries)
                    if item.id == public_id
                )
            except StopIteration as exc:
                raise InvalidPaginationError("unknown cursor") from exc

        selected = summaries[start : start + request.limit + 1]
        has_more = len(selected) > request.limit
        items = tuple(selected[: request.limit])
        next_cursor = _encode_cursor(items[-1].id) if has_more and items else None
        return ConversationPage(
            items=items,
            next_cursor=next_cursor,
            limit=request.limit,
        )

    def get_conversation(self, public_id: str) -> ConversationDetail | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM conversations WHERE public_id = ?",
                (public_id,),
            ).fetchone()
            if row is None:
                rows = conn.execute(
                    "SELECT * FROM conversations WHERE public_id IS NULL"
                ).fetchall()
                row = next(
                    (item for item in rows if _public_id(item) == public_id),
                    None,
                )
            if row is None:
                return None
            summary = self._summary(conn, row)
            events = self._events(conn, row["id"])
            tasks = self._tasks(events)
            activations = self._activations(events, tasks)
            return ConversationDetail(
                **summary.__dict__,
                tasks=tasks,
                skill_activations=activations,
            )
        except sqlite3.Error as exc:
            raise StoreError("store cannot be read") from exc
        finally:
            conn.close()

    def get_store_metadata(self) -> StoreMetadata:
        conn = self._connect()
        try:
            version = get_schema_version(conn)
            metadata = dict(
                conn.execute("SELECT key, value FROM ingest_meta").fetchall()
            )
            harnesses = tuple(
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT harness_id FROM conversations ORDER BY harness_id"
                )
            )
            raw_summary = metadata.get("last_ingest_summary")
            summary = None
            if raw_summary:
                values = json.loads(raw_summary)
                summary = IngestCounts(**values)
            last_ingest = _datetime(metadata.get("last_ingest_at"))
        except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            raise StoreError("store cannot be read") from exc
        finally:
            conn.close()
        if version is None:
            raise StoreIncompatibleError("missing schema version")

        return StoreMetadata(
            api_version="v1",
            schema_version=version,
            supported_schema_version=SUPPORTED_SCHEMA_VERSION,
            last_successful_ingest_at=last_ingest,
            last_ingest_summary=summary,
            harnesses=harnesses,
        )

    def _summary(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> ConversationSummary:
        events = self._events(conn, row["id"])
        tasks = self._tasks(events)
        activations = self._activations(events, tasks)
        grouped: OrderedDict[tuple[str, str], list[SkillActivation]] = OrderedDict()
        for activation in activations:
            grouped.setdefault(
                (activation.path, activation.source),
                [],
            ).append(activation)
        skills = tuple(
            SkillSummary(
                name=values[0].name,
                path=key[0],
                source=key[1],
                activation_count=len(values),
            )
            for key, values in grouped.items()
        )
        return ConversationSummary(
            id=_public_id(row),
            title=row["title"],
            harness=row["harness_id"],
            workspace_paths=tuple(json.loads(row["workspace_paths"] or "[]")),
            started_at=_datetime(row["started_at"]),
            ended_at=_datetime(row["ended_at"]),
            skills=skills,
            task_count=len(tasks),
            activation_count=len(activations),
        )

    @staticmethod
    def _events(conn: sqlite3.Connection, row_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM events WHERE conversation_id = ? ORDER BY sequence",
            (row_id,),
        ).fetchall()
        return [
            {
                **dict(row),
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]

    @staticmethod
    def _tasks(events: list[dict[str, Any]]) -> tuple[Task, ...]:
        tasks: list[Task] = []
        for event in events:
            if event["event_type"] != "task.recorded":
                continue
            tasks.append(
                Task(
                    id=event["event_id"],
                    turn_index=event["turn_index"]
                    if event["turn_index"] is not None
                    else len(tasks),
                    text=event["payload"].get("raw_text", ""),
                    submitted_at=_datetime(event["occurred_at"]),
                    time_provenance=_time_provenance(event["time_provenance"]),
                )
            )
        return tuple(sorted(tasks, key=lambda task: task.turn_index))

    @staticmethod
    def _activations(
        events: list[dict[str, Any]],
        tasks: tuple[Task, ...],
    ) -> tuple[SkillActivation, ...]:
        task_by_turn = {task.turn_index: task.id for task in tasks}
        resources: dict[str, list[SkillResourceRead]] = {}
        for event in events:
            if event["event_type"] != "skill.resource_read":
                continue
            body = event["payload"]
            parent = body.get("parent_activation_id")
            if not parent:
                continue
            resources.setdefault(parent, []).append(
                SkillResourceRead(
                    id=event["event_id"],
                    path=body["path"],
                    sequence=event["sequence"],
                    read_at=_datetime(event["occurred_at"]),
                    time_provenance=_time_provenance(event["time_provenance"]),
                    payload=_payload(
                        body.get("payload_snapshot") or body.get("payload")
                    ),
                )
            )

        activations = []
        for event in events:
            if event["event_type"] != "skill.activated":
                continue
            body = event["payload"]
            activation_id = event["event_id"]
            activations.append(
                SkillActivation(
                    id=activation_id,
                    task_id=task_by_turn.get(event["turn_index"]),
                    turn_index=event["turn_index"],
                    sequence=event["sequence"],
                    activated_at=_datetime(event["occurred_at"]),
                    time_provenance=_time_provenance(event["time_provenance"]),
                    path=body["path"],
                    source=_source(
                        body.get("source_bucket", body.get("source", "unknown"))
                    ),
                    name=body.get("name", body.get("skill_name")),
                    description=body.get(
                        "description",
                        body.get("skill_description"),
                    ),
                    payload=_payload(
                        body.get("payload_snapshot") or body.get("payload")
                    ),
                    resource_reads=tuple(resources.get(activation_id, ())),
                )
            )
        return tuple(activations)
