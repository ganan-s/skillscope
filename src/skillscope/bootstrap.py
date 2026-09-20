"""Composition root for concrete Skillscope adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from skillscope.api.app import create_app
from skillscope.application.ingest import IngestConversations, IngestSummary
from skillscope.application.ports import DiscoveryContext
from skillscope.application.queries import (
    GetConversation,
    GetStoreMetadata,
    ListConversations,
)
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.readers import SQLiteReadRepository
from skillscope.storage.repositories import SQLiteSnapshotWriter


def ingest_cursor(
    *,
    context: DiscoveryContext,
    db_path: Path,
    now: datetime | None = None,
) -> IngestSummary:
    from skillscope.plugins.cursor.plugin import CursorPlugin

    conn = connect_writable(db_path)
    try:
        migrate(conn)
        conn.commit()
        writer = SQLiteSnapshotWriter(conn)
        operation = IngestConversations(
            plugin=CursorPlugin(),
            writer=writer,
            metadata_writer=writer,
        )
        return operation(context=context, now=now or datetime.now(UTC))
    finally:
        conn.close()


def build_api_app(db_path: Path, *, static_dir: Path | None = None) -> FastAPI:
    repository = SQLiteReadRepository(db_path)
    return create_app(
        list_conversations=ListConversations(repository),
        get_conversation=GetConversation(repository),
        get_store_metadata=GetStoreMetadata(repository),
        static_dir=static_dir,
    )


def validate_read_store(db_path: Path) -> None:
    """Validate serve compatibility without creating or migrating the store."""
    SQLiteReadRepository(db_path).get_store_metadata()


def build_evaluation(
    *, project: Path, cases: Path, evidence: Path | None, output: Path
):
    """Wire the standalone pilot without giving serve access to live files."""
    from skillscope.application.evaluation import EvaluateSkills
    from skillscope.evaluation.files import FileEvaluationSink, FileEvaluationSource

    return EvaluateSkills(
        source=FileEvaluationSource(project, cases, evidence),
        sink=FileEvaluationSink(output),
    )
