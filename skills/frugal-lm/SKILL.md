---
name: frugal-lm
description: Use when calling cloud LLMs in batch with structured output and resilience - fallback chains across free/local/paid tiers, round-robin load balancing across providers, or per-call failure isolation. Trigger whenever the user mentions LLM batch jobs, rotating free endpoints, provider fallback, or structured output with fault tolerance.
license: MIT
compatibility: Requires Python 3.11+, pydantic-ai, and at least one of OPENROUTER_API_KEY or KILO_API_KEY. Optional local fallback via LM Studio (LMSTUDIO_BASE_URL).
metadata:
  author: dushyantkhosla
  version: "1.0"
---

# frugal-lm - Structured LLM Fallback Pattern

Batch pipeline that tries cloud LLMs in priority order (free rotating → local → paid), falls through on failure, returns `None` if all options exhausted. Built on PydanticAI with OpenAI-compatible providers.

## File Structure

```
lm/
  chain.py    # resolve_model_chain(mode) → Iterator of ModelEntry
  client.py   # call_cloud_structured() - iterates chain, first success wins
```

Caller (e.g. `ops/screen.py`) loops over jobs, handles `None`, logs, continues.

---

## Core Types

```python
from typing import TypeVar, Type, Iterator
from pydantic import BaseModel
from dataclasses import dataclass
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.vercel import VercelProvider
from pydantic_ai.settings import ModelSettings

T = TypeVar("T", bound=BaseModel)

@dataclass
class ModelEntry:
    label: str                  # human-readable, e.g. "openrouter:free-0"
    model: OpenAIChatModel
    settings: ModelSettings
```

---

## Provider Registry

Use a dataclass registry — single resolver, no duplicated logic.

```python
from dataclasses import dataclass, field
import random

@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    provider_type: str  # "openai" or "vercel"
    base_url: str | None = None   # only for openai type
    models_env: str | None = None  # env var for model list
    models_default: str = ""
    local_fallback: bool = False

    def get_models(self) -> list[str]:
        env_val = os.getenv(self.models_env or "") if self.models_env else ""
        models_str = env_val or self.models_default
        return [m.strip() for m in models_str.split(",") if m.strip()]

PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        name="ollama",
        api_key_env="OLLAMA_API_KEY",
        provider_type="openai",
        base_url="https://ollama.com/v1",
        models_env="OLLAMA_MODELS",
        # Verified accessible free models (tested 2025-05-12)
        # From 39 cloud models tested, 14 are accessible on free plan
        # Full set: gemma4:31b,gpt-oss:120b,gpt-oss:20b,minimax-m2,minimax-m2.5,ministral-3:14b,devstral-2:123b,devstral-small-2:24b,nemotron-3-nano:30b,nemotron-3-super,qwen3-coder-next,qwen3-next:80b,qwen3-vl:235b,qwen3-vl:235b-instruct
        models_default="gpt-oss:120b,gemma4:31b,ministral-3:14b,minimax-m2.5,minimax-m2,devstral-2:123b,qwen3-next:80b",
    ),
    "vercel-ai-gateway": ProviderConfig(
        name="vercel-ai-gateway",
        api_key_env="VERCEL_AI_GATEWAY_API_KEY",
        provider_type="vercel",
        models_env="VERCEL_MODELS",
        models_default="deepseek/deepseek-v4-flash,xiaomi/mimo-v2-flash,zai/glm-4.7-flash,openai/gpt-5-nano,google/gemini-2.5-flash-lite",
    ),
    "openrouter:free": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        provider_type="openai",
        base_url="https://openrouter.ai/api/v1",
        models_env="OPENROUTER_MODEL_FREE",
        models_default="openrouter/auto",
        local_fallback=True,
    ),
    "openrouter:paid": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        provider_type="openai",
        base_url="https://openrouter.ai/api/v1",
        models_env="OPENROUTER_MODEL_PAID",
        models_default="deepseek/deepseek-v4-flash",
    ),
    "kilo:free": ProviderConfig(
        name="kilo",
        api_key_env="KILO_API_KEY",
        provider_type="openai",
        base_url=os.getenv("KILO_BASE_URL", "https://api.kilo.ai/v1"),
        models_env="KILO_MODEL_FREE",
        models_default="kilo-auto/free",
        local_fallback=True,
    ),
    "kilo:paid": ProviderConfig(
        name="kilo",
        api_key_env="KILO_API_KEY",
        provider_type="openai",
        base_url=os.getenv("KILO_BASE_URL", "https://api.kilo.ai/v1"),
        models_env="KILO_MODEL_PAID",
        models_default="deepseek/deepseek-v4-flash",
    ),
}

def resolve_model_chain(mode: str) -> Iterator[ModelEntry]:
    config = PROVIDERS.get(mode)
    if not config:
        return

    api_key = os.getenv(config.api_key_env)
    if not api_key:
        return

    models = random.sample(config.get_models(), len(config.get_models()))

    for model_name in models:
        provider = (
            VercelProvider(api_key=api_key)
            if config.provider_type == "vercel"
            else OpenAIProvider(base_url=config.base_url, api_key=api_key)
        )
        yield ModelEntry(
            label=f"{config.name}:{model_name}",
            model=OpenAIChatModel(model_name, provider=provider),
            settings=ModelSettings(timeout=30.0),
        )

    # Local fallback at end of chain (for free tiers)
    if config.local_fallback:
        entry = _local_entry()
        if entry:
            yield entry
```
```

**Local entry helper** — returns `None` silently when `LOCAL_MODEL_INFERENCE` is unset:

```python
def _local_entry() -> ModelEntry | None:
    model_name = os.getenv("LOCAL_MODEL_INFERENCE")
    if not model_name:
        return None
    return ModelEntry(
        label="local",
        model=OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
                api_key="lm-studio",
            )
        ),
        settings=ModelSettings(timeout=60.0),   # local models are slower
    )
```

---

## Structured Call

```python
async def call_cloud_structured(
    system_prompt: str,
    user_prompt: str,
    output_type: Type[T],   # must be a BaseModel subclass, e.g. class JobScore(BaseModel): ...
    mode: str,
) -> T | None:
    """
    Returns structured output on first success, None if all models fail.
    Never raises - all LLM exceptions are caught internally.
    """
    retries = 5 if "free" in mode else 3   # free endpoints rotate, so more retries = more model diversity
    for entry in resolve_model_chain(mode):
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
            continue   # try next entry in chain
    return None
```

---

## Failure Handling - 3 Layers

| Layer | Mechanism | Outcome |
|---|---|---|
| `Agent(retries=N)` | PydanticAI internal retry on 5xx / parse failure | Succeeds or raises after N attempts |
| Chain loop | `except Exception: continue` to next `ModelEntry` | First success wins; returns `None` if chain exhausted |
| Caller batch loop | `if result is None: log_failure(row); continue` | Batch never halts; failed rows logged for review |

**Circuit breaker (optional, recommended for large batches):**

Track consecutive failures per provider in module-level state. Skip a provider for 60s after 5 consecutive failures. Per-model tracking is useless on rotating free endpoints - track per-provider label instead.

```python
from collections import defaultdict
import time

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
        _failures[provider] = 0
```

Plug into `call_cloud_structured`: check `_is_blocked(entry.label.split(":")[0])` before each attempt; call `_record_failure` in the `except` block.

---

## Load Balancing - Round-Robin Across Modes

Splits rows across mode pools before dispatch. Each pool gets its own concurrency semaphore, so failures in one don't stall the other.

```python
async def run_batch(rows: list[dict], modes: list[str] = None) -> list[T | None]:
    modes = modes or ["openrouter:free", "kilo:free"]
    chunks: dict[str, list] = {m: [] for m in modes}

    for i, row in enumerate(rows):
        chunks[modes[i % len(modes)]].append(row)

    async def process_chunk(chunk: list, mode: str) -> list[T | None]:
        sem = asyncio.Semaphore(10)
        async def one(row):
            async with sem:
                return await call_cloud_structured(..., mode=mode)
        return list(await asyncio.gather(*[one(r) for r in chunk], return_exceptions=True))

    results_by_mode = await asyncio.gather(*[
        process_chunk(chunks[m], m) for m in modes
    ])

    # re-interleave into original order
    flat: list[T | None] = [None] * len(rows)
    for mode_idx, mode in enumerate(modes):
        for chunk_idx, row_idx in enumerate(
            i for i, _ in enumerate(rows) if i % len(modes) == mode_idx
        ):
            flat[row_idx] = results_by_mode[mode_idx][chunk_idx]
    return flat
```

---

## Model Discovery (Refreshing the Ollama Pool)

Ollama Cloud's free model availability changes over time. To dynamically discover which models are currently accessible on the free plan:

```python
import os
import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

async def discover_ollama_free_models() -> list[str]:
    """Fetch all cloud models from Ollama API, test each, return free ones."""
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
        if model_name.count(":") >= 2:  # skip local models with digest hashes
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

# Override the default pool after discovery:
# os.environ["OLLAMA_MODELS"] = ",".join(discovered_models)
```

Alternatively, use the standalone test scripts at `../freellm/test_ollama.py` or `../freellm/test_ollama_complete.py` to generate a list, then set `OLLAMA_MODELS` from its output.

---

## Pre-flight Check

Call before batch starts. Warns but never crashes.

```python
async def ensure_local_model_loaded() -> bool:
    """Returns True if local model is reachable, False otherwise."""
    entry = _local_entry()
    if not entry:
        return False
    try:
        agent = Agent(model=entry.model, model_settings=entry.settings, retries=1,
                      output_type=str, system_prompt="ping")
        await agent.run(user_prompt="ping")
        return True
    except Exception as e:
        logger.warning(f"Local model unavailable, will skip in chain: {e}")
        return False
```

---

## Env Config

```bash
OPENROUTER_API_KEY=sk-or-v1-...
KILO_API_KEY=eyJhbGci...
OLLAMA_API_KEY=...                              # Ollama Cloud
VERCEL_AI_GATEWAY_API_KEY=...                   # Vercel AI Gateway

# Optional — enables local fallback in free-mode chains
LOCAL_MODEL_INFERENCE=qwen3.5-9b-mlx
LMSTUDIO_BASE_URL=http://localhost:1234/v1     # default

# Optional model overrides (defaults shown)
OPENROUTER_MODEL_FREE=openrouter/auto
OPENROUTER_MODEL_PAID=deepseek/deepseek-v4-flash
KILO_MODEL_FREE=kilo-auto/free
KILO_MODEL_PAID=deepseek/deepseek-v4-flash
KILO_BASE_URL=https://api.kilo.ai/v1

# Ollama Cloud models (comma-separated, shuffled at runtime)
# Full set of 14 verified accessible free models:
#   gemma4:31b,gpt-oss:120b,gpt-oss:20b,minimax-m2,minimax-m2.5,
#   ministral-3:14b,devstral-2:123b,devstral-small-2:24b,
#   nemotron-3-nano:30b,nemotron-3-super,qwen3-coder-next,
#   qwen3-next:80b,qwen3-vl:235b,qwen3-vl:235b-instruct
OLLAMA_MODELS=gpt-oss:120b,gemma4:31b,ministral-3:14b,minimax-m2.5,minimax-m2,devstral-2:123b,qwen3-next:80b

# Vercel AI Gateway models (comma-separated, shuffled at runtime)
VERCEL_MODELS=deepseek/deepseek-v4-flash,xiaomi/mimo-v2-flash,zai/glm-4.7-flash,openai/gpt-5-nano,google/gemini-2.5-flash-lite
```

---

## Design Rules

- **Return `None`, don't raise** - caller decides skip vs abort; LLM exceptions never escape `call_cloud_structured`
- **Sequential chain, never concurrent** - free tiers have quota limits; paid costs money; concurrency is per-pool, not per-model
- **Fresh `Agent()` per call** - never reuse across rows
- **Free tier needs more retries** - each retry may hit a different rotating model; use `retries=5`
- **Local fallback is optional** - absent `LOCAL_MODEL_INFERENCE` means silently skipped, never a crash
- **Pre-flight local model** - call `ensure_local_model_loaded()` before batch; log warning on failure, continue anyway

## Limitations

- **Free endpoint latency is unpredictable** - rotating models vary widely; set per-call timeouts in `ModelSettings`
- **Local fallback adds cold-start risk** - LM Studio may need a warm-up call; `ensure_local_model_loaded()` handles this
- **Circuit breaker state is in-process** - not shared across workers; use Redis if running multi-process
- **`return_exceptions=True` in gather** - exceptions from `process_chunk` become values; check `isinstance(r, Exception)` when consuming results
