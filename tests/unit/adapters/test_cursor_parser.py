from __future__ import annotations

from skillscope.plugins.cursor.parser import (
    native_content,
    native_turn_ended,
    native_user_text,
)


def test_native_user_text_from_message_content_blocks_returns_text() -> None:
    record = {
        "role": "user",
        "message": {
            "content": [{"type": "text", "text": "Explain the repository."}],
        },
    }

    assert native_user_text(record) == "Explain the repository."
    assert native_content(record) == [
        {"type": "text", "text": "Explain the repository."}
    ]


def test_native_user_text_from_user_query_wrapper_strips_tags() -> None:
    record = {
        "role": "user",
        "content": "<user_query>\nAdd a login form\n</user_query>",
    }

    assert native_user_text(record) == "Add a login form"


def test_native_user_text_from_plain_content_string_returns_text() -> None:
    record = {"role": "user", "content": "What is 2 + 2?"}

    assert native_user_text(record) == "What is 2 + 2?"


def test_native_user_text_when_content_missing_returns_none() -> None:
    assert native_user_text({"role": "user"}) is None
    assert native_user_text({"role": "user", "message": {}}) is None


def test_native_turn_ended_from_top_level_record_returns_status() -> None:
    assert native_turn_ended({"type": "turn_ended", "status": "error"}) == "error"


def test_native_turn_ended_from_nested_message_returns_status() -> None:
    assert (
        native_turn_ended({"message": {"type": "turn_ended", "status": "success"}})
        == "success"
    )


def test_native_turn_ended_when_status_is_unrecognized_returns_unknown() -> None:
    assert native_turn_ended({"type": "turn_ended", "status": "aborted"}) == "unknown"


def test_native_turn_ended_when_record_is_not_turn_close_returns_none() -> None:
    assert native_turn_ended({"role": "assistant"}) is None
