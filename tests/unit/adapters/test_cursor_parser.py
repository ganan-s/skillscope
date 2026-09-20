from __future__ import annotations

from skillscope.plugins.cursor.parser import native_content, native_user_text


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
