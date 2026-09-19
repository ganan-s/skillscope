from __future__ import annotations

import pytest

from skillscope.application.queries import (
    ConversationNotFoundError,
    GetConversation,
    InvalidPaginationError,
    PageRequest,
)


class EmptyReader:
    def get_conversation(self, public_id: str) -> None:
        return None


def test_page_request_when_limit_is_outside_contract_rejects_request() -> None:
    with pytest.raises(InvalidPaginationError):
        PageRequest(limit=101)


def test_get_conversation_when_reader_has_no_match_raises_stable_error() -> None:
    operation = GetConversation(EmptyReader())

    with pytest.raises(ConversationNotFoundError):
        operation("conv_missing")
