"""Tests for agent markdown library sync endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.schema import Content
from app.repositories import favorites_repository


def _make_content() -> Content:
    return Content(
        content_type="article",
        url="https://example.com/how-agents-work",
        title="How Agents Work",
        source="New York Times",
        publication_date=datetime(2026, 4, 3, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None),
        status="completed",
        content_metadata={
            "content": "Raw body text from the article.",
            "summary": {
                "summary_kind": "default",
                "summary_version": "v1",
                "title": "How Agents Work",
                "overview": "A compact summary of how agents work.",
                "full_markdown": "# How Agents Work\n\nA compact summary of how agents work.\n",
            },
        },
    )


def test_agent_library_manifest_defaults_to_summary_only(
    client,
    db_session,
    test_user,
) -> None:
    """Manifest should return only summary markdown unless source export is requested."""
    content = _make_content()
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    favorites_repository.add_favorite(db_session, content.id, test_user.id)

    response = client.get("/api/agent/library/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"]
    assert len(payload["documents"]) == 1
    document = payload["documents"][0]
    assert document["variant"] == "summary"
    assert document["content_id"] == content.id
    assert document["relative_path"].endswith(f"__summary__c{content.id}.md")
    assert document["checksum_sha256"]


def test_agent_library_manifest_can_include_source_and_download_document(
    client,
    db_session,
    test_user,
) -> None:
    """Library sync should expose both manifest metadata and file contents."""
    content = _make_content()
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    favorites_repository.add_favorite(db_session, content.id, test_user.id)

    manifest_response = client.get(
        "/api/agent/library/manifest",
        params={"include_source": "true"},
    )

    assert manifest_response.status_code == 200
    documents = manifest_response.json()["documents"]
    assert len(documents) == 2

    source_document = next(document for document in documents if document["variant"] == "source")
    file_response = client.get(
        "/api/agent/library/file",
        params={"path": source_document["relative_path"]},
    )

    assert file_response.status_code == 200
    payload = file_response.json()
    assert payload["relative_path"] == source_document["relative_path"]
    assert payload["variant"] == "source"
    assert "Raw body text from the article." in payload["text"]
