"""Tests for apps/core/tokens.py."""

from apps.core.tokens import TOKEN_LENGTH, make_token


def test_make_token_is_url_safe_and_unique() -> None:
    tokens = {make_token() for _ in range(50)}
    assert len(tokens) == 50
    for token in tokens:
        assert len(token) == TOKEN_LENGTH
        assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
