"""SQLite connection and migration management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SQL_DIR = Path(__file__).parent / "sql"
SUPPORTED_SCHEMA_VERSION = 2


def _migration_files() -> list[Path]:
    """Return ordered SQL migration files."""
    return sorted(_SQL_DIR.glob("*.sql"))


def connect_writable(db_path: Path) -> sqlite3.Connection:
    """Open a writable connection with WAL, FK, and busy timeout."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a read-only connection."""
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    """Return the current schema version, or None if not initialised."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations and return the resulting schema version.

    Idempotent: skips already-applied migrations.
    """
    current = get_schema_version(conn)
    if current is not None and current > SUPPORTED_SCHEMA_VERSION:
        raise RuntimeError(
            f"store schema {current} is newer than supported {SUPPORTED_SCHEMA_VERSION}"
        )
    if current == SUPPORTED_SCHEMA_VERSION:
        return current

    for mig_file in _migration_files():
        migration_version = int(mig_file.name.split("_", maxsplit=1)[0])
        if current is not None and migration_version <= current:
            continue
        sql = mig_file.read_text(encoding="utf-8")
        conn.executescript(sql)

    version = get_schema_version(conn)
    if version is None:
        raise RuntimeError("Migration failed: schema_meta is empty")
    return version
