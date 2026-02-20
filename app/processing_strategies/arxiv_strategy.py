"""Strategy for processing arXiv content URLs."""

from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx  # For type hinting httpx.Headers
from google import genai
from google.genai.types import Part

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.services.langfuse_tracing import (
    extract_google_usage_details,
    langfuse_generation_context,
)

logger = get_logger(__name__)
settings = get_settings()


class ArxivProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing arXiv URLs, whether they are abstract pages or direct PDFs.
    Abstract links are normalized to their PDF counterparts before download.
    """

    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
        self._logger_prefix = "ArxivStrategy"

    def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool:
        """
        Determines if this strategy can handle the given URL.
        """
        parsed = urlparse(url)
        if not self._is_arxiv_host(parsed.netloc):
            logger.debug("%s cannot handle URL (not arXiv host): %s", self._logger_prefix, url)
            return False

        path = parsed.path.lower()
        if path.startswith("/abs/") or path.startswith("/pdf/"):
            logger.debug("%s can handle URL: %s", self._logger_prefix, url)
            return True

        logger.debug("%s cannot handle URL (unsupported path): %s", self._logger_prefix, url)
        return False

    def preprocess_url(self, url: str) -> str:
        """
        Normalize arXiv URLs so downstream processing always receives a direct PDF URL.
        """
        parsed = urlparse(url)
        if not self._is_arxiv_host(parsed.netloc):
            logger.warning(
                "%s: preprocess_url called with non-arXiv host %s; returning unchanged.",
                self._logger_prefix,
                url,
            )
            return url

        path = parsed.path
        lower_path = path.lower()
        target_path = path
        target_query = parsed.query

        if lower_path.startswith("/abs/"):
            target_path = f"/pdf/{path[5:]}"
            target_query = ""
            logger.info(
                "%s: Converted arXiv abstract URL %s to PDF path %s",
                self._logger_prefix,
                url,
                target_path,
            )
        elif lower_path.startswith("/pdf/"):
            target_path = f"/pdf/{path[5:]}"
        else:
            logger.warning(
                "%s: preprocess_url received unsupported arXiv path %s; returning unchanged.",
                self._logger_prefix,
                url,
            )
            return url

        normalized = parsed._replace(
            scheme="https" if parsed.scheme in ("", "http") else parsed.scheme,
            netloc="arxiv.org",
            path=target_path,
            params="",
            query=target_query,
            fragment="",
        )
        return urlunparse(normalized)

    def download_content(self, url: str) -> bytes:  # PDF content is bytes
        """
        Downloads the PDF content from the given URL.
        This method expects 'url' to be a direct link to a PDF file
        (transformed by preprocess_url if it was an abstract page).
        """
        logger.info(f"ArxivStrategy: Downloading PDF content from {url}")
        response = self.http_client.get(url)
        # RobustHttpClient handles raise_for_status
        logger.info(
            f"ArxivStrategy: Successfully downloaded PDF from {url}. Final URL: {response.url}"
        )
        return response.content

    def extract_data(self, content: bytes, url: str) -> dict[str, Any]:
        """
        Prepares PDF data for LLM processing.
        No local text extraction - the LLM will handle everything from the PDF bytes.
        """
        logger.info("ArxivStrategy: Preparing PDF data for LLM processing for URL: %s", url)

        if not content:
            logger.warning(f"ArxivStrategy: No PDF content provided for {url}")
            return {
                "title": "Extraction Failed (No PDF Content)",
                "text_content": None,
                "content_type": "pdf",
                "final_url_after_redirects": url,
                "pdf_bytes": None,
            }

        google_api_key = getattr(settings, "google_api_key", None)
        model_name = getattr(settings, "pdf_gemini_model", "gemini-3-flash-preview")
        if google_api_key:
            try:
                client = genai.Client(api_key=google_api_key)
                pdf_part = Part.from_bytes(data=content, mime_type="application/pdf")
                extraction_prompt = """
                Extract all text content from this PDF document.
                Return the full text in a clean, readable format.
                Preserve the document structure (headings, paragraphs, lists).
                If you can identify the title, include it at the beginning.
                """
                with langfuse_generation_context(
                    name="queue.arxiv.extract_text",
                    model=model_name,
                    input_data=extraction_prompt,
                    metadata={"source": "queue", "url": url},
                ) as generation:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[pdf_part, extraction_prompt],
                        config={"temperature": 0.3, "max_output_tokens": 50000},
                    )
                    usage_details = extract_google_usage_details(response)
                    response_text = getattr(response, "text", None)
                    if generation is not None:
                        generation.update(
                            output=response_text[:400] if isinstance(response_text, str) else None,
                            usage_details=usage_details,
                        )
                text_content = response.text if hasattr(response, "text") else ""
                if text_content:
                    lines = text_content.strip().split("\n")
                    title = lines[0][:200] if lines else "ArXiv PDF Document"
                    logger.info(
                        "ArxivStrategy: Extracted text via Gemini for %s. Title: %s...",
                        url,
                        title[:50],
                    )
                    return {
                        "title": title,
                        "author": None,
                        "publication_date": None,
                        "text_content": text_content,
                        "content_type": "pdf",
                        "final_url_after_redirects": url,
                    }
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc).lower()
                if (
                    "failed_precondition" in error_message
                    or "user location is not supported" in error_message
                ):
                    logger.warning(
                        (
                            "ArxivStrategy: Gemini extraction unavailable for %s; "
                            "falling back to raw PDF bytes: %s"
                        ),
                        url,
                        exc,
                    )
                else:
                    logger.error("ArxivStrategy: Gemini extraction failed for %s: %s", url, exc)
        else:
            logger.warning(
                "ArxivStrategy: Google API key missing; cannot extract PDF text for %s",
                url,
            )

        # Use filename from URL as a fallback title - LLM will extract the real title
        parsed_url = urlparse(url)
        filename = parsed_url.path.split("/")[-1] or "ArXiv PDF Document"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        logger.info(
            "ArxivStrategy: Successfully prepared PDF data for %s. Fallback title: %s",
            url,
            filename,
        )
        return {
            "title": filename,  # Fallback title - LLM will extract the real title
            "author": None,
            "publication_date": None,
            "text_content": "",
            "content_type": "pdf",
            "final_url_after_redirects": url,
            "pdf_bytes": content,  # Store raw PDF bytes for LLM processing
        }

    def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepares PDF data for LLM processing.
        Passes raw PDF bytes directly to the LLM for title extraction and summarization.
        """
        final_url = extracted_data.get("final_url_after_redirects", "Unknown URL")
        logger.info("ArxivStrategy: Preparing PDF data for LLM for URL: %s", final_url)
        text_content = extracted_data.get("text_content") or ""
        if isinstance(text_content, str) and text_content.strip():
            return {
                "content_to_filter": text_content,
                "content_to_summarize": text_content,
                "is_pdf": True,
            }

        pdf_bytes = extracted_data.get("pdf_bytes")

        if pdf_bytes is None:
            logger.error("ArxivStrategy: PDF bytes not found in extracted_data for %s", final_url)
            return {
                "content_to_filter": None,  # PDFs skip text-based filtering
                "content_to_summarize": b"",  # Empty bytes as fallback
                "is_pdf": True,
            }

        return {
            "content_to_filter": None,  # PDFs skip text-based filtering
            "content_to_summarize": pdf_bytes,  # Pass raw PDF bytes to LLM
            "is_pdf": True,
        }

    def extract_internal_urls(self, content: bytes, original_url: str) -> list[str]:
        """
        Extracts internal URLs. For PDFs, this is typically not applicable in the same
        way as HTML, so an empty list is returned.
        """
        logger.info(
            "ArxivStrategy: extract_internal_urls called for %s (PDF). Returning empty list.",
            original_url,
        )
        return []

    def _is_arxiv_host(self, netloc: str) -> bool:
        """Return True if the provided netloc belongs to arxiv.org."""
        normalized = netloc.lower()
        return normalized == "arxiv.org" or normalized.endswith(".arxiv.org")
