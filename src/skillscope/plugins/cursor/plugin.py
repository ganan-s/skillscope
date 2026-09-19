"""Cursor harness plugin implementing the HarnessPlugin protocol."""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from skillscope.domain.models import (
    ConversationSnapshot,
    EligibilityVerdict,
    IngestEligibility,
    ReadinessBasis,
)
from skillscope.plugins.base import (
    ConversationRef,
    DiscoveryContext,
    Platform,
)
from skillscope.plugins.cursor.paths import find_transcript_dirs
from skillscope.plugins.cursor.parser import (
    _parse_spool_records,
    _extract_session_metadata,
    build_conversation_snapshot,
)


class CursorPlugin:
    """Cursor harness adapter: discovery, eligibility, and snapshot."""

    @property
    def id(self) -> str:
        return "cursor"

    def detect_platform(self) -> Platform:
        return Platform(os=sys.platform, harness="cursor")

    def discover(self, context: DiscoveryContext) -> Iterable[ConversationRef]:
        """Find Cursor conversations from transcripts and hook spool.

        Joins by conversation_id so a conversation may have transcript-only,
        hook-only, or both.
        """
        seen: dict[str, ConversationRef] = {}

        # 1. Discover transcript conversations
        transcript_root = context.transcript_override
        if transcript_root is None:
            cursor_root = context.home / ".cursor" / "projects"
            transcript_root = cursor_root

        if transcript_root.is_dir():
            # Try standard Cursor projects layout first
            conv_dirs = find_transcript_dirs(transcript_root)

            # Fallback: treat override as a flat directory of conversation dirs
            if not conv_dirs and context.transcript_override:
                for child in sorted(transcript_root.iterdir()):
                    if child.is_dir() and list(child.glob("*.jsonl")):
                        conv_dirs.append(child)

            for conv_dir in conv_dirs:
                conv_id = conv_dir.name
                seen[conv_id] = ConversationRef(
                    harness_id="cursor",
                    native_conversation_id=conv_id,
                    source_locators=(conv_dir,),
                    extra={"transcript_dir": str(conv_dir)},
                )

        # 2. Add/merge spool conversations
        spool_path = context.spool_override
        if spool_path is None:
            from skillscope.config import default_spool_path
            spool_path = default_spool_path()

        if spool_path.exists():
            with spool_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = rec.get("payload", {})
                    cid = payload.get("conversation_id", payload.get("session_id"))
                    if cid and cid not in seen:
                        seen[cid] = ConversationRef(
                            harness_id="cursor",
                            native_conversation_id=cid,
                            source_locators=(),
                            extra={"spool_only": True},
                        )
                    elif cid and cid in seen:
                        existing = seen[cid]
                        if "spool_only" not in existing.extra:
                            # Mark that we have both sources
                            seen[cid] = ConversationRef(
                                harness_id=existing.harness_id,
                                native_conversation_id=existing.native_conversation_id,
                                source_locators=existing.source_locators,
                                extra={**existing.extra, "has_spool": True},
                            )

        yield from seen.values()

    def inspect(
        self,
        conversation: ConversationRef,
        *,
        now: datetime,
        context: DiscoveryContext,
    ) -> IngestEligibility:
        """Decide if a conversation is ready to ingest."""
        conv_id = conversation.native_conversation_id

        # Check hook spool for sessionEnd
        spool_path = context.spool_override
        if spool_path is None:
            from skillscope.config import default_spool_path
            spool_path = default_spool_path()

        spool_records = []
        if spool_path.exists():
            spool_records = _parse_spool_records(spool_path, conv_id)

        meta = _extract_session_metadata(spool_records)
        if meta["has_session_end"]:
            return IngestEligibility(
                verdict=EligibilityVerdict.READY,
                basis=ReadinessBasis.NATIVE_END,
            )

        # Check quiescence: transcript must exist and not have been modified
        # within grace_seconds
        transcript_dir = conversation.extra.get("transcript_dir")
        if transcript_dir:
            td = Path(transcript_dir)
            jsonl_files = list(td.glob("*.jsonl"))
            if jsonl_files:
                latest_mtime = max(f.stat().st_mtime for f in jsonl_files)
                age = (now - datetime.fromtimestamp(latest_mtime, tz=timezone.utc)).total_seconds()
                if age >= context.grace_seconds:
                    return IngestEligibility(
                        verdict=EligibilityVerdict.READY,
                        basis=ReadinessBasis.QUIESCENT,
                    )
                return IngestEligibility(
                    verdict=EligibilityVerdict.DEFER,
                    reason=f"transcript modified {age:.0f}s ago, grace={context.grace_seconds}s",
                )

        # Spool-only with no session end: defer
        if conversation.extra.get("spool_only"):
            return IngestEligibility(
                verdict=EligibilityVerdict.DEFER,
                reason="spool-only conversation without sessionEnd",
            )

        return IngestEligibility(
            verdict=EligibilityVerdict.REJECT,
            reason="no transcript or session end found",
        )

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot:
        """Build a canonical snapshot from available sources."""
        conv_id = conversation.native_conversation_id

        transcript_path = None
        transcript_dir = conversation.extra.get("transcript_dir")
        if transcript_dir:
            transcript_path = Path(transcript_dir)

        spool_path = context.spool_override
        if spool_path is None:
            from skillscope.config import default_spool_path
            spool_path = default_spool_path()

        snap, _ = build_conversation_snapshot(
            conv_id,
            transcript_path,
            spool_path,
        )
        return snap
