---
name: frugal-lm
description: Use when calling cloud LLMs in batch with structured output and resilience — fallback chains across free/local/paid tiers, round-robin load balancing across providers, or per-call failure isolation. Trigger whenever the user mentions LLM batch jobs, rotating free endpoints, provider fallback, or structured output with fault tolerance.
license: MIT
compatibility: Requires Python 3.11+, pydantic-ai, and at least one of OPENROUTER_API_KEY or KILO_API_KEY. Optional local fallback via LM Studio (LMSTUDIO_BASE_URL).
metadata:
  author: dushyantkhosla
  version: "1.0"
---

# frugal-lm — Structured LLM Fallback Pattern

Batch pipeline that tries cloud LLMs in priority order (free rotating → local → paid), falls through on failure, returns `None` if all options exhausted. Built on PydanticAI with OpenAI-compatible providers.

## File Structure

```
lm/
  chain.py    # resolve_model_chain(mode) → Iterator of ModelEntry
  client.py   # call_cloud_structured() — iterates chain, first success wins
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
from pydantic_ai.settings import ModelSettings

T = TypeVar("T", bound=BaseModel)

@dataclass
class ModelEntry:
    label: str                  # human-readable, e.g. "openrouter:free-0"
    model: OpenAIChatModel
    settings: ModelSettings
```

---

## Model Chain Resolution

`resolve_model_chain(mode)` yields `ModelEntry` instances in priority order. Each call is a fresh iterator — no shared state.

**Mode strings:** `"openrouter:free"` | `"openrouter:paid"` | `"kilo:free"` | `"kilo:paid"` | `"local"`

**Free mode chain:** `free rotating → local (if configured) → paid`  
**Paid mode chain:** `[paid]` — single entry, no fallback  
**Local mode chain:** `[local]` — single entry  

```python
def resolve_model_chain(mode: str) -> Iterator[ModelEntry]:
    if mode == "local":
        entry = _local_entry()
        if entry:
            yield entry
        return

    provider, tier = mode.split(":")
    base_url, api_key = _provider_config(provider)

    if tier == "paid":
        candidates = [_paid_model_name(provider)]
    else:
        candidates = [
            _free_model_name(provider),   # rotating endpoint, $0
            None,                          # local placeholder — filled below
            _paid_model_name(provider),   # safety net, costs $
        ]

    for i, model_name in enumerate(candidates):
        if model_name is None:
            # inject local fallback at index 1 when LOCAL_MODEL_INFERENCE is set
            entry = _local_entry()
            if entry:
                yield entry
            continue

        yield ModelEntry(
            label=f"{provider}:{tier}-{i}",
            model=OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(base_url=base_url, api_key=api_key)
            ),
            settings=ModelSettings(timeout=30.0),
        )
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
    Never raises — all LLM exceptions are caught internally.
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

## Failure Handling — 3 Layers

| Layer | Mechanism | Outcome |
|---|---|---|
| `Agent(retries=N)` | PydanticAI internal retry on 5xx / parse failure | Succeeds or raises after N attempts |
| Chain loop | `except Exception: continue` to next `ModelEntry` | First success wins; returns `None` if chain exhausted |
| Caller batch loop | `if result is None: log_failure(row); continue` | Batch never halts; failed rows logged for review |

**Circuit breaker (optional, recommended for large batches):**

Track consecutive failures per provider in module-level state. Skip a provider for 60s after 5 consecutive failures. Per-model tracking is useless on rotating free endpoints — track per-provider label instead.

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

## Load Balancing — Round-Robin Across Modes

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

# Optional — enables local fallback in free-mode chains
LOCAL_MODEL_INFERENCE=qwen3.5-9b-mlx
LMSTUDIO_BASE_URL=http://localhost:1234/v1     # default

# Optional model overrides (defaults shown)
OPENROUTER_MODEL_FREE=openrouter/auto
OPENROUTER_MODEL_PAID=deepseek/deepseek-v4-flash
KILO_MODEL_FREE=kilo-auto/free
KILO_MODEL_PAID=deepseek/deepseek-v4-flash
KILO_BASE_URL=https://api.kilo.ai/v1
```

---

## Design Rules

- **Return `None`, don't raise** — caller decides skip vs abort; LLM exceptions never escape `call_cloud_structured`
- **Sequential chain, never concurrent** — free tiers have quota limits; paid costs money; concurrency is per-pool, not per-model
- **Fresh `Agent()` per call** — never reuse across rows
- **Free tier needs more retries** — each retry may hit a different rotating model; use `retries=5`
- **Local fallback is optional** — absent `LOCAL_MODEL_INFERENCE` means silently skipped, never a crash
- **Pre-flight local model** — call `ensure_local_model_loaded()` before batch; log warning on failure, continue anyway

## Limitations

- **Free endpoint latency is unpredictable** — rotating models vary widely; set per-call timeouts in `ModelSettings`
- **Local fallback adds cold-start risk** — LM Studio may need a warm-up call; `ensure_local_model_loaded()` handles this
- **Circuit breaker state is in-process** — not shared across workers; use Redis if running multi-process
- **`return_exceptions=True` in gather** — exceptions from `process_chunk` become values; check `isinstance(r, Exception)` when consuming results
