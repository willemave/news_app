"""Tests for title normalization helpers."""

from app.utils.title_utils import clean_title


def test_clean_title_drops_url_only_title() -> None:
    assert clean_title("https://t.co/1HuCDkyzQG https://t.co/B8fxN1yI8e") is None


def test_clean_title_keeps_textual_title_with_link_suffix() -> None:
    assert (
        clean_title("Pichai on search, portfolio of long term initiatives: https://t.co/t39iO9B7Ld")
        == "Pichai on search, portfolio of long term initiatives: https://t.co/t39iO9B7Ld"
    )
