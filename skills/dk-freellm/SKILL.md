---
name: dk-freellm
description: Lightweight free LLM pool — interleaves free endpoints (openrouter/auto, kilo-auto/free, ollama cloud, vercel ai gateway, groq, cerebras, google gemini) with in-memory circuit breaker. Use when you need a single free provider with fallback, no paid models.
license: MIT
compatibility: Requires Python 3.11+, pydantic-ai, and at least one of the free providers configured.
metadata:
  author: dushyantkhosla
  version: "1.1"
---

# freellm — Free LLM Pool

Interleaved free LLM pool. Single generator, no paid models, in-memory circuit breaker.

Unlike `frugal-lm` (batch pipelines with multi-tier fallback), this is a lightweight singleton pool for single-call use cases where you just want "any working free model".

**This is not a library** — it documents patterns. Agents implement the variant they need (cursor vs pipeline, raw calls vs structured output, etc.).

## File Structure

```
freellm/
  pool.py    # Pool class with generator, circuit breaker
  client.py  # call_free_structured() — wrapper using pool
```

---

## Pool

```python
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterator
import time

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.vercel import VercelProvider


@dataclass
class ModelEntry:
    label: str
    model: OpenAIChatModel


@dataclass
class ProviderConfig:
    api_key_env: str
    provider_type: str  # "openai" | "vercel"
    base_url: str | None = None


# Single-entry free providers (model rotation handled internally)
SINGLE_PROVIDERS: dict[str, ProviderConfig] = {
    "openrouter": ProviderConfig(
        api_key_env="OPENROUTER_API_KEY",
        provider_type="openai",
        base_url="https://openrouter.ai/api/v1",
    ),
    "kilo": ProviderConfig(
        api_key_env="KILO_API_KEY",
        provider_type="openai",
        base_url=None,  # resolved from KILO_BASE_URL
    ),
    "groq": ProviderConfig(
        api_key_env="GROQ_API_KEY",
        provider_type="openai",
        base_url="https://api.groq.com/openai/v1",
    ),
}

# Multi-model free providers (we shuffle the pool)
MULTI_PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        api_key_env="OLLAMA_API_KEY",
        provider_type="openai",
        base_url="https://ollama.com/v1",
    ),
    "vercel-ai-gateway": ProviderConfig(
        api_key_env="VERCEL_AI_GATEWAY_API_KEY",
        provider_type="vercel",
        base_url=None,
    ),
    "groq": ProviderConfig(
        api_key_env="GROQ_API_KEY",
        provider_type="openai",
        base_url="https://api.groq.com/openai/v1",
    ),
    "cerebras": ProviderConfig(
        api_key_env="CEREBRAS_API_KEY",
        provider_type="openai",
        base_url="https://api.cerebras.ai/v1",
    ),
    "google": ProviderConfig(
        api_key_env="GOOGLE_API_KEY",
        provider_type="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
}

MODEL_POOLS: dict[str, list[str]] = {
    "ollama": [
        # Verified accessible free models (tested 2025-05-12)
        "gemma4:31b",
        "gpt-oss:120b",
        "gpt-oss:20b",
        "minimax-m2",
        "minimax-m2.5",
        "ministral-3:14b",
        "devstral-2:123b",
        "devstral-small-2:24b",
        "nemotron-3-nano:30b",
        "nemotron-3-super",
        "qwen3-coder-next",
        "qwen3-next:80b",
        "qwen3-vl:235b",
        "qwen3-vl:235b-instruct",
    ],
    "vercel-ai-gateway": [
        "deepseek/deepseek-v4-flash",
        "xiaomi/mimo-v2-flash",
        "zai/glm-4.7-flash",
        "openai/gpt-5-nano",
        "google/gemini-2.5-flash-lite",
    ],
    "groq": [
        # Models from test-groq.py (verified free on Groq, 2025-05-15)
        "openai/gpt-oss-120b",
        "qwen/qwen3-32b",
        "llama-3.3-70b-versatile",
    ],
    "cerebras": [
        # Verified accessible free models (tested 2026-05-22)
        "gpt-oss-120b",
        "qwen-3-235b-a22b-instruct-2507",
        "llama3.1-8b",
        "zai-glm-4.7",
    ],
    "google": [
        # Free tier models via OpenAI-compatible endpoint (tested 2026-05-22)
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ],
}


# --- Circuit breaker state (module-level, in-memory) ---

_failures: dict[str, int] = defaultdict(int)
_blocked_until: dict[str, float] = defaultdict(float)
CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN = 60.0


def _is_blocked(provider: str) -> bool:
    return time.monotonic() < _blocked_until[provider]


def _record_failure(provider: str) -> None:
    _failures[provider] += 1
    if _failures[provider] >= CIRCUIT_THRESHOLD:
        _blocked_until[provider] = time.monotonic() + CIRCUIT_COOLDOWN


def _reset_failure(provider: str) -> None:
    _failures[provider] = 0


def _build_provider(base_url: str | None, api_key: str, provider_type: str):
    if provider_type == "vercel":
        return VercelProvider(api_key=api_key)
    # openai type
    resolved_base = base_url or os.getenv("KILO_BASE_URL", "https://api.kilo.ai/v1")
    return OpenAIProvider(base_url=resolved_base, api_key=api_key)


class FreeLLMPool:
    """
    Interleaved free LLM pool with in-memory circuit breaker.

    Usage:
        pool = FreeLLMPool()
        for entry in pool.entries():
            # use entry.model, entry.label, entry.settings
            ...
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._entries: list[ModelEntry] = []
        self._built = False

    def _ensure_built(self) -> None:
        if self._built:
            return

        entries: list[ModelEntry] = []

        # Single-entry providers
        for name, config in SINGLE_PROVIDERS.items():
            api_key = os.getenv(config.api_key_env)
            if not api_key or _is_blocked(name):
                continue
            provider = _build_provider(config.base_url, api_key, config.provider_type)
            model_name = {
                "openrouter": "openrouter/auto",
                "kilo": "kilo-auto/free",
                "groq": "llama-3.3-70b-versatile",
            }.get(name, "openrouter/auto")
            entries.append(
                ModelEntry(
                    label=name,
                    model=OpenAIChatModel(model_name, provider=provider),
                )
            )

        # Multi-model providers — shuffle independently
        multi_by_provider: dict[str, list[ModelEntry]] = {}
        for name, models in MODEL_POOLS.items():
            config = MULTI_PROVIDERS[name]
            api_key = os.getenv(config.api_key_env)
            if not api_key or _is_blocked(name):
                continue
            provider = _build_provider(config.base_url, api_key, config.provider_type)
            multi_by_provider[name] = [
                ModelEntry(
                    label=f"{name}:{m}",
                    model=OpenAIChatModel(m, provider=provider),
                )
                for m in self._rng.sample(models, len(models))
            ]

        # Interleave: round-robin across providers
        if multi_by_provider:
            max_len = max(len(v) for v in multi_by_provider.values())
            for i in range(max_len):
                for name in multi_by_provider:
                    if i < len(multi_by_provider[name]):
                        entries.append(multi_by_provider[name][i])

        self._entries = entries
        self._built = True

    def entries(self) -> Iterator[ModelEntry]:
        """Yields ModelEntry instances in interleaved order. Shuffled once on first call."""
        self._ensure_built()
        yield from self._entries

    def record_failure(self, label: str) -> None:
        """Record a failure for a provider (uses first segment of label)."""
        provider = label.split(":")[0]
        _record_failure(provider)
        # Invalidate so next call rebuilds without blocked provider
        self._built = False

    def reset(self) -> None:
        """Clear circuit breaker state and rebuild pool."""
        _failures.clear()
        _blocked_until.clear()
        self._built = False
```

---

## Client

Uses PydanticAI's built-in `FallbackModel` — tries each model in sequence, falls back on failure. No manual loop needed.

```python
from typing import TypeVar, Type
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.exceptions import FallbackExceptionGroup

T = TypeVar("T", bound=BaseModel)


async def call_free_structured(
    system_prompt: str,
    user_prompt: str,
    output_type: Type[T],
    retries: int = 5,
    pool: FreeLLMPool | None = None,
) -> T | None:
    """
    Uses FreeLLMPool, tries each entry in order, returns first success or None.
    Caller handles None (skip, log, retry later).
    """
    pool = pool or FreeLLMPool()
    entries = list(pool.entries())
    if not entries:
        return None

    model = (
        FallbackModel(entries[0].model, *[e.model for e in entries[1:]], fallback_on=(Exception,))
        if len(entries) > 1
        else entries[0].model
    )

    agent = Agent(
        model=model,
        retries=retries,
        output_type=output_type,
        system_prompt=system_prompt,
    )
    try:
        result = await agent.run(user_prompt=user_prompt)
        return result.output
    except FallbackExceptionGroup:
        # All models failed — record failures for circuit breaker
        for entry in entries:
            pool.record_failure(entry.label)
        return None
```

---

## Batch Processing with Shared Cursor

For single-call use cases, `call_free_structured()` is sufficient. For batch jobs with concurrent workers, use a **shared cursor** so callers naturally round-robin across providers instead of all hitting the same first entry:

```python
pool = FreeLLMPool()
cursor = iter(pool.entries())  # single cursor, shared across tasks
cursor_lock = asyncio.Lock()

async def next_model() -> ModelEntry:
    async with cursor_lock:
        return next(cursor)  # round-robins across providers naturally

async def classify_one(job):
    entry = await next_model()
    agent = Agent(model=entry.model, ...)
    return await agent.run(job.text)
```

**References**: For full batch pipelines with load balancing, semaphores, and mode chains, see the `frugal-lm` skill. The shared-cursor pattern here is the lightweight alternative — one pool, multiple consumers.

---

## When to Use freellm vs frugal-lm

| You need... | Use |
|-------------|-----|
| Single call, any free model works | `freellm.call_free_structured()` |
| Batch job, shared cursor, simple | `freellm` + shared cursor pattern |
| Batch job, mode chains, load balancing, paid fallback | `frugal-lm` |
| Per-call tier selection (free → local → paid) | `frugal-lm` |

---

## Known Circuit Breaker Limitations

The built-in circuit breaker protects against cascading failures but has rough edges. Agents should handle these when implementing freellm:

- **429 (rate limit) counts as failure** — In production, agents should catch 429s, sleep 1-2s, and retry the same model *without* calling `record_failure()`. Otherwise a brief rate limit burst trips the breaker.
- **Post-cooldown stuck state** — After 60s, the provider is unblocked but its failure count remains at 5. One more failure immediately re-blocks it. Agents should reset the count after cooldown expires, or call `pool.reset()` periodically.
- **401/403 (auth) burns 5 failures** — Auth errors should probably trip the circuit instantly, not burn retries.
- **Provider-level only** — One bad Ollama model blocks all 14. For fine-grained control, agents can track model-level failures separately.

---

## Extension Points for Agents

When implementing freellm, the agent may want to:

- **Filter the pool by capability** — For simple text classification, exclude vision models (`qwen3-vl:235b`, etc.) and >100B params to reduce latency.
- **Add shared cursor API** — Wrap `entries()` in a thread-safe cursor with `asyncio.Lock`.
- **Add rate-limit backoff** — Catch 429, sleep, retry; only 5xx/timeout should count as failures.
- **Add per-tier timeouts** — 15s for small models, 30s for large models.
- **Add cooldown-reset logic** — Clear failure counts when the block period expires so providers get a fair retry.
- **Compose with frugal-lm** — The pool + cursor pattern can be dropped into a `frugal-lm`-style batch runner when tiered fallback is needed.

---

## Env Config

```bash
# At least one required
OPENROUTER_API_KEY=sk-or-v1-...
KILO_API_KEY=eyJhbGci...
OLLAMA_API_KEY=...
VERCEL_AI_GATEWAY_API_KEY=...
GROQ_API_KEY=gsk_your_groq_api_key
CEREBRAS_API_KEY=csk_your_cerebras_api_key
GOOGLE_API_KEY=AIzaSy...

# Optional overrides
KILO_BASE_URL=https://api.kilo.ai/v1          # kilo default

# Optional model overrides (comma-separated, shuffled at runtime)
# Default Ollama free models (14 verified accessible models)
# Full list: gemma4:31b,gpt-oss:120b,gpt-oss:20b,minimax-m2,minimax-m2.5,ministral-3:14b,devstral-2:123b,devstral-small-2:24b,nemotron-3-nano:30b,nemotron-3-super,qwen3-coder-next,qwen3-next:80b,qwen3-vl:235b,qwen3-vl:235b-instruct
OLLAMA_MODELS=gpt-oss:120b,gemma4:31b,ministral-3:14b,minimax-m2.5,minimax-m2,devstral-2:123b,qwen3-next:80b
VERCEL_MODELS=deepseek/deepseek-v4-flash,xiaomi/mimo-v2-flash,openai/gpt-5-nano,google/gemini-2.5-flash-lite
GROQ_MODELS=openai/gpt-oss-120b,qwen/qwen3-32b,llama-3.3-70b-versatile
CEREBRAS_MODELS=gpt-oss:120b,qwen-3-235b-a22b-instruct-2507,llama3.1-8b,zai-glm-4.7
GOOGLE_MODELS=gemini-2.5-flash-lite,gemini-2.5-flash
```

---

## Model Discovery (Refreshing the Pool)

Ollama Cloud's free model availability changes over time. To find which models are currently accessible:

```python
import httpx
import asyncio

async def fetch_accessible_free_models() -> list[str]:
    """Fetch all cloud models from Ollama API, test each, return free ones."""
    import os
    from pydantic import BaseModel
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    class Check(BaseModel):
        ok: bool

    async with httpx.AsyncClient() as client:
        r = await client.get("https://ollama.com/api/tags")
        models = [m["name"] for m in r.json().get("models", []) if m.get("name")]

    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        return []

    free = []
    for model_name in models:
        if model_name.count(":") >= 2:  # skip digest-hash local models
            continue
        try:
            model = OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(base_url="https://ollama.com/v1", api_key=api_key),
            )
            agent = Agent(model, output_type=Check, retries=1)
            await agent.run("hi")
            free.append(model_name)
        except Exception:
            pass
    return free
```

Then update `MODEL_POOLS["ollama"]` with the result, or override via `OLLAMA_MODELS` env var at runtime.

### Model Discovery — Groq

```python
import httpx, os

r = httpx.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
)
for m in r.json()["data"]:
    if m["active"]:
        print(m["id"])
```

### Model Discovery — Cerebras

```python
import requests

r = requests.get(
    "https://api.cerebras.ai/v1/models",
    headers={"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY']}"},
)
for m in r.json()["data"]:
    print(m["id"])
```

Update `MODEL_POOLS["cerebras"]` with the results, or override via `CEREBRAS_MODELS` env var at runtime.

### Test Scripts

Two standalone scripts in this directory let you discover accessible free models:

- **`test_ollama.py`** — interactive test with filtering options (cloud models only)
- **`test_ollama_complete.py`** — tests ALL models from the API

```bash
cd freellm && python3 test_ollama_complete.py
```

Results are saved as JSON alongside the scripts.

---

## Design Rules

- **No paid models** — only free-tier endpoints
- **`FallbackModel` for fallback** — don't write manual `for entry in pool: try/except/continue` loops; use PydanticAI's built-in `FallbackModel`
- **Single-entry rotation** — `openrouter/auto`, `kilo-auto/free`, and `llama-3.3-70b-versatile` rotate internally via the provider; we treat them as single entries
- **Interleaved multi-model** — Ollama, Vercel, Groq, Cerebras, and Google have explicit model pools; entries are shuffled once, then interleaved (one from each per round)
- **Circuit breaker per provider** — blocks provider for 60s after 5 consecutive failures; pool auto-rebuilds on next `entries()` call
- **Pool is stateless** — `FreeLLMPool()` is a lightweight factory; create a new instance or call `.reset()` to rebuild
- **Not a library** — this skill documents patterns; agents implement the variant they need (cursor vs pipeline, raw calls vs structured output, etc.)
- **Composable with frugal-lm** — the pool + cursor pattern can be dropped into a `frugal-lm`-style batch runner when tiered fallback is needed
