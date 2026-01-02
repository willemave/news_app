"""Tests for ArxivProcessorStrategy PDF extraction."""

from types import SimpleNamespace
from unittest.mock import Mock

from app.processing_strategies import arxiv_strategy as arxiv
from app.processing_strategies.arxiv_strategy import ArxivProcessorStrategy


def test_arxiv_extract_data_uses_gemini_when_available(monkeypatch):
    class DummyModels:
        def generate_content(self, model, contents, config):  # noqa: ANN001
            return SimpleNamespace(text="Paper Title\nBody text")

    class DummyClient:
        def __init__(self, api_key: str):  # noqa: ANN001
            self.models = DummyModels()

    class DummyPart:
        @staticmethod
        def from_bytes(data, mime_type):  # noqa: ANN001
            return "PDFPART"

    class DummySettings:
        google_api_key = "test-key"
        pdf_gemini_model = "gemini-3-flash-preview"

    monkeypatch.setattr(arxiv, "genai", SimpleNamespace(Client=DummyClient))
    monkeypatch.setattr(arxiv, "Part", DummyPart)
    monkeypatch.setattr(arxiv, "settings", DummySettings())

    strategy = ArxivProcessorStrategy(http_client=Mock())
    result = strategy.extract_data(b"%PDF-1.4", "https://arxiv.org/pdf/2407.12220.pdf")

    assert result["content_type"] == "pdf"
    assert result["text_content"].startswith("Paper Title")
    assert result["title"] == "Paper Title"
