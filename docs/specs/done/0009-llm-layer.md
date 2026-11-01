# Spec 0009: Add the LLM layer

- **Status**: done
- **Depends on**: 0001
- **Blocks**: 0010
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

The agents that explain results (and, later, propose attacks) need a language model. The layer must work
with the providers people already have keys for, cost nothing and need no network by default, never
spend past a cap, return the same answer for the same request, prove which prompt produced an answer,
and reject any number the model did not take from the evidence.

## 2. User stories

- As a user with an OpenAI, Anthropic or xAI key, I want to set two variables and get real memos.
- As a user without keys, I want everything to run, clearly in simulated mode.
- As a reviewer, I want every figure in a memo traced to a stored result.

## 3. Applicable rules

- `RULE-BUDGET-01`: per-run and monthly caps; past them the client answers in simulated mode.
- `RULE-AUDIT-01`: `audit_numbers` rejects figures that are not in the evidence.
- `RULE-LLM-01`: the layer only produces text; nothing in it decides a verdict.

## 4. Contracts and data model

- `LLMRequest` (system, prompt, `max_output_tokens`, `fallback_text`) and `LLMResponse` (text, provider,
  model, input, output and cached tokens, cost, `from_cache`).
- Providers: `simulated` (answers with the deterministic draft), `openai`, `xai` (OpenAI-compatible at
  `https://api.x.ai/v1`), `openai_compatible` (any base URL: OpenRouter, OpenCode Zen, local servers) and
  `anthropic` (official SDK, system prompt marked for prompt caching, refusals raised).
- SQLite at `QMAS_DATA_DIR/llm.sqlite3`: exact cache keyed by the SHA-256 of provider, model and request
  (never overwritten) and a spend table by month.
- Prompts ship in `qmas/prompts/*.md` with `prompts.lock.json`; a changed prompt refuses to load.
- Settings: `QMAS_LLM_PROVIDER`, `QMAS_LLM_MODEL`, `QMAS_LLM_BASE_URL`, `QMAS_LLM_API_KEY`,
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, token prices, caps, timeout and cache switch.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.llm.build_client(settings)` | Client for the configured provider. |
| Python | `qmas.llm.PromptRegistry` | `render`, `hash`, `lock`. |
| Python | `qmas.llm.audit_numbers(text, allowed)` | Number audit. |

## 6. Acceptance criteria

- [x] Every provider maps its SDK response; tests use fakes and no network.
- [x] Cache hits are free and marked; budgets fall back to simulated mode; monthly spend persists.
- [x] Prompts are hash-locked; the packaged prompts match their lock.
- [x] The number audit accepts rounded figures and percentages and rejects invented ones.
- [x] `.env.example` documents every variable, including the planned market-data keys.
- [x] `uv run poe check` passes.

## 7. Required tests

Provider mapping (OpenAI-compatible, Anthropic, refusal), provider selection and configuration errors,
key variables, cache, budget per run and per month, simulated warning, prompt registry, number audit.

## 8. Out of scope

- The reporter agent that uses this layer: spec 0010. LLM-proposed attacks: spec 0012.
- Streaming and tool use: one short completion per call is enough here.

## Post-implementation notes

- The user asked for GPT (OpenAI), Claude (Anthropic) and Grok (xAI) keys to be ready. OpenAI and xAI
  share the OpenAI-compatible provider; Anthropic uses its official SDK.
- Model ids are not hard-coded except the Anthropic example (`claude-opus-5-5`) and the default prices
  (USD 4 / 20 per million tokens). Users set the model and its prices.
- `.env.example` also documents the planned market-data keys (Alpaca as primary, SEC EDGAR user agent);
  nothing reads them yet.
