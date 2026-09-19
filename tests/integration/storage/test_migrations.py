from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from skillscope.storage.connection import (
    SUPPORTED_SCHEMA_VERSION,
    connect_readonly,
    connect_writable,
    get_schema_version,
    migrate,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_migrate_when_store_is_version_one_applies_additive_migration(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    conn = connect_writable(db_path)
    initial_sql = (
        PROJECT_ROOT / "src" / "skillscope" / "storage" / "sql" / "001_initial.sql"
    ).read_text()
    conn.executescript(initial_sql)

    version = migrate(conn)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
    assert version == SUPPORTED_SCHEMA_VERSION
    assert "public_id" in columns
    conn.close()


def test_readonly_connection_when_write_is_attempted_rejects_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    writable = connect_writable(db_path)
    migrate(writable)
    writable.close()
    readonly = connect_readonly(db_path)

    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        readonly.execute("INSERT INTO ingest_meta (key, value) VALUES ('test', 'test')")

    assert get_schema_version(readonly) == SUPPORTED_SCHEMA_VERSION
    readonly.close()
