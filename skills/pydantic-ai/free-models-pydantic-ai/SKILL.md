---
name: free-models-pydantic-ai
description: >
  Use free cloud LLM providers (OpenRouter, Kilo) with Pydantic AI for structured output extraction.
  Provides agent configuration patterns using OpenAI-compatible API with free tier models.
  Use when user wants free inference, budget-conscious AI, or exploring free LLM options.
license: MIT
compatibility: Requires Python 3.10+, pydantic-ai, python-dotenv
metadata:
  version: "1.0.0"
  author: opencode
---

# Free Models with Pydantic AI

Use free cloud LLM providers (OpenRouter, Kilo) as backends with Pydantic AI to extract structured data from text.

## When to Use This Skill

Invoke this skill when:
- User wants free LLM inference with Pydantic AI
- User mentions free models, OpenRouter, Kilo, or budget-conscious AI
- User asks to extract structured data from text without OpenAI/Anthropic costs
- Exploring multiple free LLM providers

Do **not** use this skill for:
- Paid LLM providers (use `building-pydantic-ai-agents` instead)
- Local inference (use `lm-studio-pydantic-ai` instead)
- Non-Pydantic AI frameworks

## Prerequisites

```bash
uv add "pydantic-ai-slim[openai]" python-dotenv
```

## Available Free Model Providers

### OpenRouter

```bash
free_models_openrouter() {
    python -c "import requests;r = requests.get('https://openrouter.ai/api/v1/models');[print(d['id']) for d in r.json()['data'] if d['id'].endswith('free')]"
}
```

### Kilo

```bash
free_models_kilo() {
    python -c "import requests;r = requests.get('https://api.kilo.ai/api/gateway/models');[print(d['id']) for d in r.json()['data'] if d['isFree']]"
}
```

## Quick-Start Patterns

### Kilo Provider

```python
# kilo_agent.py
import os
from pydantic import BaseModel
from typing import List
from dotenv import find_dotenv, load_dotenv

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.exceptions import UnexpectedModelBehavior

load_dotenv(find_dotenv())


class PersonInfo(BaseModel):
    name: str
    email: str
    skills: List[str]


def extract_person_info(text: str) -> PersonInfo:
    agent = Agent(
        model=OpenAIChatModel(
            os.getenv("KILO_MODEL_FREE"),
            provider=OpenAIProvider(
                base_url=os.environ["KILO_BASE_URL"],
                api_key=os.getenv("KILO_API_KEY"),
            ),
        ),
        model_settings=ModelSettings(
            thinking=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        retries=3,
        output_type=PersonInfo,
        instructions="Extract person information from the text. Return only valid JSON.",
    )

    try:
        return agent.run_sync(user_prompt=text).output
    except UnexpectedModelBehavior as exc:
        raise RuntimeError(f"Model run failed: {exc}") from exc
```

### OpenRouter Provider

```python
# openrouter_agent.py
import os
from pydantic import BaseModel
from typing import List
from dotenv import find_dotenv, load_dotenv

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.exceptions import UnexpectedModelBehavior

load_dotenv(find_dotenv())


class PersonInfo(BaseModel):
    name: str
    email: str
    skills: List[str]


def extract_person_info(text: str) -> PersonInfo:
    agent = Agent(
        model=OpenAIChatModel(
            os.getenv("OPENROUTER_MODEL_FREE"),
            provider=OpenAIProvider(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            ),
        ),
        model_settings=ModelSettings(
            thinking=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        retries=3,
        output_type=PersonInfo,
        instructions="Extract person information from the text. Return only valid JSON.",
    )

    try:
        return agent.run_sync(user_prompt=text).output
    except UnexpectedModelBehavior as exc:
        raise RuntimeError(f"Model run failed: {exc}") from exc
```

### Agent Factory Pattern

For reusable agents across providers:

```python
from typing import Type, Literal
from pydantic import BaseModel


def create_free_extractor(
    output_type: Type[BaseModel],
    instructions: str,
    provider: Literal["kilo", "openrouter"] = "openrouter",
):
    base_urls = {
        "kilo": os.environ.get("KILO_BASE_URL", "https://api.kilo.ai/v1"),
        "openrouter": "https://openrouter.ai/api/v1",
    }
    api_keys = {
        "kilo": os.getenv("KILO_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
    }
    models = {
        "kilo": os.getenv("KILO_MODEL_FREE"),
        "openrouter": os.getenv("OPENROUTER_MODEL_FREE"),
    }

    return Agent(
        model=OpenAIChatModel(
            models[provider],
            provider=OpenAIProvider(
                base_url=base_urls[provider],
                api_key=api_keys[provider],
            ),
        ),
        model_settings=ModelSettings(
            thinking=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        retries=3,
        output_type=output_type,
        instructions=instructions,
    )


class PersonInfo(BaseModel):
    name: str
    email: str
    skills: List[str]


def extract_person_info(text: str, provider: Literal["kilo", "openrouter"] = "openrouter") -> PersonInfo:
    agent = create_free_extractor(
        PersonInfo,
        "Extract person information from the text. Return only valid JSON.",
        provider=provider,
    )
    return agent.run_sync(user_prompt=text).output
```

## Environment Setup

Create `.env` in your project:

```bash
# Kilo
KILO_BASE_URL=https://api.kilo.ai/v1
KILO_API_KEY=your-kilo-api-key
KILO_MODEL_FREE=your-preferred-kilo-free-model

# OpenRouter
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL_FREE=your-preferred-openrouter-free-model
```

## Configuration Reference

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `KILO_BASE_URL` | Kilo API endpoint | `https://api.kilo.ai/v1` |
| `KILO_API_KEY` | Kilo API key | Get from kilo.ai |
| `KILO_MODEL_FREE` | Kilo free model | `meta-llama/llama-3.2-1b-instruct` |
| `OPENROUTER_API_KEY` | OpenRouter API key | Get from openrouter.ai |
| `OPENROUTER_MODEL_FREE` | OpenRouter free model | `google/gemma-3-4b-it:free` |
| `thinking=False` | Disable chain-of-thought | Clean JSON output |
| `extra_body` | Model-specific flags | `{"chat_template_kwargs": {"enable_thinking": False}}` |
| `retries=3` | Handle output errors | Graceful failures |

## Common Extraction Patterns

### Extracting Named Entities

```python
from pydantic import BaseModel
from typing import List


class EntityExtraction(BaseModel):
    persons: List[str]
    organizations: List[str]
    locations: List[str]
    dates: List[str]


def extract_entities(text: str, provider: Literal["kilo", "openrouter"] = "openrouter") -> EntityExtraction:
    agent = create_free_extractor(
        EntityExtraction,
        "Extract named entities from the text. Return only valid JSON.",
        provider=provider,
    )
    return agent.run_sync(user_prompt=text).output
```

### Sentiment Analysis

```python
from pydantic import BaseModel
from typing import List


class SentimentResult(BaseModel):
    sentiment: str
    confidence: float
    key_phrases: List[str]


def analyze_sentiment(text: str, provider: Literal["kilo", "openrouter"] = "openrouter") -> SentimentResult:
    agent = create_free_extractor(
        SentimentResult,
        "Analyze the sentiment of the text. Return only valid JSON.",
        provider=provider,
    )
    return agent.run_sync(user_prompt=text).output
```

### Document Classification

```python
from pydantic import BaseModel
from typing import List


class ClassificationResult(BaseModel):
    category: str
    subcategory: str
    confidence: float
    reasons: List[str]


def classify_document(text: str, provider: Literal["kilo", "openrouter"] = "openrouter") -> ClassificationResult:
    agent = create_free_extractor(
        ClassificationResult,
        "Classify the document into categories. Return only valid JSON.",
        provider=provider,
    )
    return agent.run_sync(user_prompt=text).output
```

## Troubleshooting

### Rate Limits

Free tiers have rate limits. Consider:
- Adding delays between requests
- Implementing exponential backoff
- Switching providers when one is rate-limited

### Unexpected Output / Garbage

- Use `thinking=False` in ModelSettings
- Add `"enable_thinking": False` to `extra_body` for Qwen/Gemma models
- Make instructions more explicit: "Return ONLY valid JSON matching the schema."
- Add post-processing: `sorted(set(...))` to deduplicate results

### API Key Issues

Ensure API keys are set in `.env` and `load_dotenv(find_dotenv())` is called before accessing them.

## Generic File Structure Template

```
project/
├── .env                    # API keys and model selection
├── models.py               # Pydantic output schemas
├── prompts.py              # Agent instructions
├── agents/
│   ├── kilo_agent.py
│   └── openrouter_agent.py
├── extractors/
│   ├── entity_extractor.py
│   ├── sentiment_extractor.py
│   └── classifier.py
└── main.py                 # Entry point
```

---

## Example Use Case: CV/JD Matching Pipeline

*This section demonstrates a real-world application using the patterns above. It's project-specific — adapt the schemas and logic for your own use case.*

### Use Case Overview

Score CVs against job descriptions and generate edit plans to maximize ATS matching using free models:

```python
# models.py - Project-specific schemas
from pydantic import BaseModel
from typing import List

class KeywordExtraction(BaseModel):
    skills_technology: List[str]
    skills_domain: List[str]

class JDMeta(BaseModel):
    role_summary: str
    key_responsibilities: List[str]
    skills_must_have: List[str]
    experience_requirements: List[str]

class ATSScore(BaseModel):
    total: float
    semantic_sim: float
    missing_technology: List[str]
    missing_domain: List[str]

class EditPlan(BaseModel):
    injections: List[str]
    rephrases: List[str]
    new_bullets: List[str]
```

### Pipeline Flow

```python
# 1. Extract CV keywords (one-time)
from cv_extractor import extract_cv, save_extraction

cv = extract_cv("data/cv.yml")
save_extraction(cv, "data/cv.yml")

# 2. Extract JD metadata + keywords (per job)
from jd_extractor import load_all_jd_rows, extract_jd

rows = load_all_jd_rows("data/jobs/")
for row in rows:
    jd = extract_jd(row)

# 3. Score and tailor
from ats_score import score
from cv_tailor import generate_edit_plan

s = score(cv, jd)
plan = generate_edit_plan(cv, jd, s)
```

### Project File Structure

```
project/
├── .env
├── models.py              # Project-specific schemas
├── prompts.py             # Custom instructions per extraction
├── cv_extractor.py        # CV extraction logic
├── jd_extractor.py        # JD extraction logic
├── ats_score.py           # Scoring logic
├── cv_tailor.py           # Edit plan generation
├── data/
│   ├── cv/
│   └── jd/
└── main.py
```

This pattern scales to any document extraction pipeline using free LLM providers. Replace the schemas and prompts for your domain.