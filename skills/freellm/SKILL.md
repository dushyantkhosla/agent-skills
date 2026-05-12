---
name: freellm
description: Lightweight free LLM pool — interleaves free endpoints (openrouter/auto, kilo-auto/free, ollama cloud, vercel ai gateway) with in-memory circuit breaker. Use when you need a single free provider with fallback, no paid models.
license: MIT
compatibility: Requires Python 3.11+, pydantic-ai, and at least one of the free providers configured.
metadata:
  author: dushyantkhosla
  version: "1.0"
---

# freellm — Free LLM Pool

Interleaved free LLM pool. Single generator, no paid models, in-memory circuit breaker.

Unlike `frugal-lm` (batch pipelines with multi-tier fallback), this is a lightweight singleton pool for single-call use cases where you just want "any working free model".

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
from pydantic_ai.settings import ModelSettings


@dataclass
class ModelEntry:
    label: str
    model: OpenAIChatModel
    settings: ModelSettings


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
            model_name = "openrouter/auto" if name == "openrouter" else "kilo-auto/free"
            entries.append(
                ModelEntry(
                    label=name,
                    model=OpenAIChatModel(model_name, provider=provider),
                    settings=ModelSettings(timeout=30.0),
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
                    settings=ModelSettings(timeout=30.0),
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

```python
from typing import TypeVar, Type
from pydantic import BaseModel
from pydantic_ai import Agent

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
    for entry in pool.entries():
        agent = Agent(
            model=entry.model,
            model_settings=entry.settings,
            retries=retries,
            output_type=output_type,
            system_prompt=system_prompt,
        )
        try:
            result = await agent.run(user_prompt=user_prompt)
            return result.output
        except Exception:
            pool.record_failure(entry.label)
            continue
    return None
```

---

## Env Config

```bash
# At least one required
OPENROUTER_API_KEY=sk-or-v1-...
KILO_API_KEY=eyJhbGci...
OLLAMA_API_KEY=...
VERCEL_AI_GATEWAY_API_KEY=...

# Optional overrides
KILO_BASE_URL=https://api.kilo.ai/v1          # kilo default

# Optional model overrides (comma-separated, shuffled at runtime)
# Default Ollama free models (14 verified accessible models)
# Full list: gemma4:31b,gpt-oss:120b,gpt-oss:20b,minimax-m2,minimax-m2.5,ministral-3:14b,devstral-2:123b,devstral-small-2:24b,nemotron-3-nano:30b,nemotron-3-super,qwen3-coder-next,qwen3-next:80b,qwen3-vl:235b-instruct
OLLAMA_MODELS=gpt-oss:120b,gemma4:31b,ministral-3:14b,minimax-m2.5,minimax-m2,devstral-2:123b,qwen3-next:80b
VERCEL_MODELS=deepseek/deepseek-v4-flash,xiaomi/mimo-v2-flash,openai/gpt-5-nano,google/gemini-2.5-flash-lite
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
- **Single-entry rotation** — `openrouter/auto` and `kilo-auto/free` rotate internally via the provider; we treat them as single entries
- **Interleaved multi-model** — Ollama and Vercel have explicit model pools; entries are shuffled once, then interleaved (one from each per round)
- **Circuit breaker per provider** — blocks provider for 60s after 5 consecutive failures; pool auto-rebuilds on next `entries()` call
- **Pool is stateless** — `FreeLLMPool()` is a lightweight factory; create a new instance or call `.reset()` to rebuild