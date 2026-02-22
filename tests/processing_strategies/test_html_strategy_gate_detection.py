"""Tests for HTML access-gate detection heuristics."""

from app.processing_strategies.html_strategy import HtmlProcessorStrategy


def test_detect_access_gate_from_javascript_notice() -> None:
    """JS-required gate pages should be flagged as extraction failures."""
    reason = HtmlProcessorStrategy._detect_access_gate(  # pylint: disable=protected-access
        title="[AINews] Anthropic's Agent Autonomy study - Latent.Space",
        text_content=(
            "This site requires JavaScript to run correctly. "
            "Please turn on JavaScript or unblock scripts."
        ),
        html_content="<html><body>This site requires JavaScript to run correctly.</body></html>",
    )

    assert reason is not None
    assert reason.startswith("access gate detected")


def test_detect_access_gate_ignores_normal_article_content() -> None:
    """Normal article content should not be mistaken for an access gate."""
    reason = HtmlProcessorStrategy._detect_access_gate(  # pylint: disable=protected-access
        title="Inside AI's $10B+ Capital Flywheel",
        text_content=(
            "Martin Casado and Sarah Wang discuss startup funding, compute contracts, "
            "model training loops, and enterprise go-to-market dynamics."
        ),
        html_content=(
            "<html><body><article>Long-form analysis about AI financing."
            "</article></body></html>"
        ),
    )

    assert reason is None
