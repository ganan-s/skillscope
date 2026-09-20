"""Compatibility re-exports for the application-owned harness port."""

from skillscope.application.ports import (
    ConversationRef,
    DiscoveryContext,
    HarnessPlugin,
    Platform,
)

__all__ = [
    "ConversationRef",
    "DiscoveryContext",
    "HarnessPlugin",
    "Platform",
]
