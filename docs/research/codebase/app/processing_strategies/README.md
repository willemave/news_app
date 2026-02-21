## Purpose
Groups the pluggable URL processing strategies that download and preprocess content before it enters the LLM pipeline (HTML, RSS, PDF, social, video, images, etc.).

## Key Files
- `app/processing_strategies/base_strategy.py` – `UrlProcessorStrategy` abstract class defining `can_handle_url`, `download_content`, `extract_data`, and `prepare_for_llm` hooks.
- `registry.py` – `StrategyRegistry` that instantiates `RobustHttpClient` and registers every concrete strategy in priority order.
- Strategy modules (`arxiv_strategy.py`, `hackernews_strategy.py`, `html_strategy.py`, `pdf_strategy.py`, `processing_strategies/image_strategy.py`, `pubmed_strategy.py`, `twitter_share_strategy.py`, `youtube_strategy.py`) implement domain-specific extraction logic.

## Main Types/Interfaces
- `UrlProcessorStrategy` base class (abstract methods plus optional URL preprocessing) and accompanying `StrategyRegistry.get_strategy` lookup.
- Each concrete strategy exposes `can_handle_url`, `download_content`, `extract_data`, and `prepare_for_llm` tailored to its corner case (e.g., HN embeds, Twitter share redirects, PDF downloads, YouTube streams).

## Dependencies & Coupling
Use `RobustHttpClient` plus utilities from `app.services` (e.g., `app.services.image_generation` indirectly) and feed into `app.pipeline.worker.ContentWorker` via `get_strategy_registry`. Strategies are ordered manually, so any new strategy must be inserted in `registry.py`.

## Refactor Opportunities
The registry hard-codes strategy order and creation; introducing a configuration-driven registry or plugin discovery would make it easier to add/test new strategies without editing this file. Strategies could also share more extraction helpers (e.g., URL normalization) to reduce duplication.

Reviewed files: 11
