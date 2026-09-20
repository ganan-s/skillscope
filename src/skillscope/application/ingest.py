"""Harness-neutral ingest orchestration."""

from __future__ import annotations

import dataclasses
from datetime import datetime

from skillscope.application.ports import (
    ConversationSnapshotWriter,
    DiscoveryContext,
    HarnessPlugin,
    IngestMetadata,
    IngestMetadataWriter,
)
from skillscope.domain.models import EligibilityVerdict


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

    def metadata(self) -> IngestMetadata:
        return IngestMetadata(
            inserted=self.inserted,
            updated=self.updated,
            unchanged=self.unchanged,
            skipped=self.skipped + self.deferred,
            failed=self.failed,
        )

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


class IngestConversations:
    """Ingest ready snapshots through application ports."""

    def __init__(
        self,
        *,
        plugin: HarnessPlugin,
        writer: ConversationSnapshotWriter,
        metadata_writer: IngestMetadataWriter,
    ) -> None:
        self._plugin = plugin
        self._writer = writer
        self._metadata_writer = metadata_writer

    def __call__(
        self,
        *,
        context: DiscoveryContext,
        now: datetime,
    ) -> IngestSummary:
        summary = IngestSummary()
        refs = list(self._plugin.discover(context))

        for ref in refs:
            try:
                eligibility = self._plugin.inspect(ref, now=now, context=context)
                if eligibility.verdict == EligibilityVerdict.DEFER:
                    summary.deferred += 1
                    continue
                if eligibility.verdict == EligibilityVerdict.REJECT:
                    summary.skipped += 1
                    continue

                snapshot = self._plugin.snapshot(ref, context=context)
                result = self._writer.persist(snapshot)
                if result == "inserted":
                    summary.inserted += 1
                elif result == "updated":
                    summary.updated += 1
                elif result == "unchanged":
                    summary.unchanged += 1
                elif result == "skipped_older":
                    summary.skipped += 1
                else:
                    raise ValueError(f"unknown persistence outcome: {result}")
            except Exception:
                summary.failed += 1
                summary.errors.append(f"{ref.native_conversation_id}: ingestion_failed")

        self._metadata_writer.record_ingest(
            completed_at=now,
            summary=summary.metadata(),
        )
        return summary
