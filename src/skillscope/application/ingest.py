"""Ingest orchestration: discover, inspect, snapshot, persist."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

from skillscope.domain.models import EligibilityVerdict
from skillscope.plugins.base import DiscoveryContext, HarnessPlugin
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.repositories import UpsertResult, upsert_conversation


@dataclasses.dataclass
class IngestSummary:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    deferred: int = 0
    failed: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return self.failed > 0

    def __str__(self) -> str:
        parts = [
            f"inserted={self.inserted}",
            f"updated={self.updated}",
            f"unchanged={self.unchanged}",
            f"skipped={self.skipped}",
            f"deferred={self.deferred}",
            f"failed={self.failed}",
        ]
        return "Ingest: " + ", ".join(parts)


def run_ingest(
    plugin: HarnessPlugin,
    context: DiscoveryContext,
    db_path: Path,
) -> IngestSummary:
    """Run a full ingest batch: discover -> inspect -> snapshot -> persist."""
    summary = IngestSummary()
    now = datetime.now(timezone.utc)

    conn = connect_writable(db_path)
    try:
        migrate(conn)

        refs = list(plugin.discover(context))

        for ref in refs:
            try:
                eligibility = plugin.inspect(ref, now=now, context=context)

                if eligibility.verdict == EligibilityVerdict.DEFER:
                    summary.deferred += 1
                    continue
                if eligibility.verdict == EligibilityVerdict.REJECT:
                    summary.skipped += 1
                    continue

                snapshot = plugin.snapshot(ref, context=context)
                result = upsert_conversation(conn, snapshot)
                conn.commit()

                if result == UpsertResult.INSERTED:
                    summary.inserted += 1
                elif result == UpsertResult.UPDATED:
                    summary.updated += 1
                elif result == UpsertResult.UNCHANGED:
                    summary.unchanged += 1
                elif result == UpsertResult.SKIPPED_OLDER:
                    summary.skipped += 1

            except Exception as exc:
                conn.rollback()
                summary.failed += 1
                summary.errors.append(
                    f"{ref.native_conversation_id}: {exc}"
                )

        # Update ingest metadata
        conn.execute(
            "INSERT OR REPLACE INTO ingest_meta (key, value) VALUES (?, ?)",
            ("last_ingest_at", now.isoformat()),
        )
        conn.commit()

    finally:
        conn.close()

    return summary
