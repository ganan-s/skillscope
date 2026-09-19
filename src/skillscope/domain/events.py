"""Convenience aliases for the canonical event types.

The authoritative definitions live in models.py.  This module re-exports the
subset commonly needed when constructing events inside harness adapters.
"""

from skillscope.domain.models import (  # noqa: F401
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    Diagnostic,
    DiagnosticCode,
    Evidence,
    EvidenceQuality,
    EventType,
    PayloadSnapshot,
    PayloadStatus,
    ReadinessBasis,
    SourceBucket,
    SourceRevision,
    TimeProvenance,
)
