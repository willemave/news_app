"""Tests for content detail chat URL generation."""

from urllib.parse import parse_qs, unquote_plus, urlparse


def _get_display_title(fixture_data: dict) -> str:
    """Get the display title the same way the API does."""
    summary = fixture_data.get("content_metadata", {}).get("summary", {})
    if summary and summary.get("title"):
        return summary["title"]
    return fixture_data.get("title") or "Untitled"


def test_chat_url_includes_user_prompt(
    client,
    create_sample_content,
    sample_article_long,
):
    """Ensure user-provided prompt is prepended to the generated ChatGPT URL."""

    content = create_sample_content(sample_article_long)
    expected_title = _get_display_title(sample_article_long)

    response = client.get(
        f"/api/content/{content.id}/chat-url",
        params={"user_prompt": "Corroborate key claims using the latest sources."},
    )

    assert response.status_code == 200
    data = response.json()
    chat_url = data["chat_url"]

    parsed = urlparse(chat_url)
    q_param = parse_qs(parsed.query).get("q")

    assert q_param, "Expected 'q' query parameter in generated URL"

    decoded_prompt = unquote_plus(q_param[0])

    assert "USER PROMPT:" in decoded_prompt
    assert "Corroborate key claims using the latest sources." in decoded_prompt
    assert expected_title in decoded_prompt


def test_chat_url_without_user_prompt(client, create_sample_content, sample_article_short):
    """Ensure legacy behavior still works when no user prompt is provided."""

    content = create_sample_content(sample_article_short)
    expected_title = _get_display_title(sample_article_short)

    response = client.get(f"/api/content/{content.id}/chat-url")

    assert response.status_code == 200
    data = response.json()

    parsed = urlparse(data["chat_url"])
    q_param = parse_qs(parsed.query).get("q")

    assert q_param, "Expected 'q' query parameter in generated URL"

    decoded_prompt = unquote_plus(q_param[0])

    assert "USER PROMPT:" not in decoded_prompt
    assert expected_title in decoded_prompt
