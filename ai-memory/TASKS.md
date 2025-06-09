# Task List: Refactor Async to Sync

This plan outlines the steps to remove unnecessary `async` processing from the application, focusing on scrapers and processors. The goal is to simplify the codebase by converting the asynchronous processing pipeline to a synchronous one.

## Phase 1: Foundational Refactoring (HTTP Client & Strategies)

- [x] **Task 1.1: Refactor `RobustHttpClient` to be synchronous.**
  - **File**: [`app/http_client/robust_http_client.py`](app/http_client/robust_http_client.py)
  - **Action**: Replace `httpx.AsyncClient` with `httpx.Client`. Convert all `async def` methods to `def` and remove `await` calls.
  - **Status**: ✅ COMPLETED

- [x] **Task 1.2: Update the `UrlProcessorStrategy` base class.**
  - **File**: [`app/processing_strategies/base_strategy.py`](app/processing_strategies/base_strategy.py)
  - **Action**: Convert all `async def` abstract methods to `def`.
  - **Status**: ✅ COMPLETED

- [x] **Task 1.3: Refactor all `UrlProcessorStrategy` implementations to be synchronous.**
  - **Files**:
    - [`app/processing_strategies/arxiv_strategy.py`](app/processing_strategies/arxiv_strategy.py)
    - [`app/processing_strategies/html_strategy.py`](app/processing_strategies/html_strategy.py)
    - [`app/processing_strategies/pdf_strategy.py`](app/processing_strategies/pdf_strategy.py)
    - [`app/processing_strategies/pubmed_strategy.py`](app/processing_strategies/pubmed_strategy.py)
  - **Action**: For each implementation, change all `async def` methods to `def` and remove `await` calls.
  - **Status**: ✅ COMPLETED

## Phase 2: Application Logic Refactoring

- [x] **Task 2.1: Refactor `UrlProcessorFactory`.**
  - **File**: [`app/processing_strategies/factory.py`](app/processing_strategies/factory.py)
  - **Action**: Convert `get_strategy` from `async def` to `def` and remove `await` calls.
  - **Status**: ✅ COMPLETED

- [x] **Task 2.2: Refactor the main article processor.**
  - **File**: [`app/processor.py`](app/processor.py)
  - **Action**: Convert `process_link_from_db` from `async def` to `def` and remove `await` calls.
  - **Status**: ✅ COMPLETED

- [x] **Task 2.3: Refactor podcast processing modules.**
  - **File**: [`app/processing/podcast_downloader.py`](app/processing/podcast_downloader.py)
  - **File**: [`app/processing/podcast_converter.py`](app/processing/podcast_converter.py)
  - **Action**: Convert all `async def` methods to `def`.
  - **Status**: ✅ COMPLETED

## Phase 3: Worker & Queue Refactoring

- [x] **Task 3.1: Simplify the `queue.py` worker tasks.**
  - **File**: [`app/queue.py`](app/queue.py)
  - **Action**: Remove the `run_async_*` helper functions and the `asyncio.run()` calls. The huey tasks will now directly call the newly synchronous processor functions.
  - **Status**: ✅ COMPLETED

## Phase 4: Testing

- [x] **Task 4.1: Update all tests to be synchronous.**
  - **Directory**: `tests/`
  - **Action**: Convert all `async def` test functions to `def`, remove `@pytest.mark.asyncio`, and update mocks to reflect the synchronous nature of the new code.
  - **Status**: ✅ COMPLETED - All 115 tests now pass
