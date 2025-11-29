# LLM call sites and replacement plan

Inventory of every LLM entrypoint and the intended pydantic-ai replacement. Model specs stay unchanged (e.g., `claude-*`, `gpt-*`, `gemini-*`).

## Summarization services
- `app/services/openai_llm.py` → replace `OpenAISummarizationService.summarize_content` with pydantic-ai agent built via `llm_agents.get_summarization_agent`. Remove direct `openai` client usage.
- `app/services/anthropic_llm.py` → same rewrite; drop direct `anthropic` client.
- `app/services/google_flash.py` → same rewrite; drop direct `google.genai` client.
- `app/services/openai_llm_tmp.py` → mark legacy/remove or delegate to the shared pydantic-ai summarization helper.
- Callers:
  - `app/pipeline/worker.py` → swap to new summarization helper.
  - `app/pipeline/sequential_task_processor.py` → same swap.

## Chat / Deep Dive
- `app/services/chat_agent.py` → already pydantic-ai but streaming; refactor to use shared `llm_models.build_pydantic_model` and sync `run_sync` calls, plus updated initial suggestions prompt.
- `app/routers/api/chat.py` → drop NDJSON streaming endpoints; use sync helper that persists messages and returns DTOs.

## Tweet suggestions
- `app/services/tweet_suggestions.py` → already pydantic-ai with Google; swap direct `GoogleModel/Provider/ModelSettings` wiring for shared `llm_models.build_pydantic_model` and reuse prompt helpers.

## Tools
- `app/services/exa_client.py` used as pydantic-ai tool in `chat_agent`; keep tool function but ensure sync tool invocation works with `Agent.run_sync`.

## Planned shared modules
- `app/services/llm_models.py` → central model construction `build_pydantic_model(model_spec: str) -> tuple[Model | str, GoogleModelSettings | None]`.
- `app/services/llm_agents.py` → agent factories (`get_summarization_agent`, tweet generator, chat agent getter) that call `build_pydantic_model` and pull prompts from `llm_prompts`.
