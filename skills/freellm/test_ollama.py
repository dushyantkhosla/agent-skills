# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic-ai", "httpx"]
# ///

"""
Ollama Cloud models accessibility tester (non-interactive)
Fetches all available models from the API and tests which ones are accessible
"""

import os
import sys
import json
import asyncio
from typing import List, Tuple

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

# Load API key from environment
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = "https://ollama.com/v1"
OLLAMA_TAGS_URL = "https://ollama.com/api/tags"

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found in environment")

print(f"Base URL: {OLLAMA_BASE_URL}")
print(f"API Key: {OLLAMA_API_KEY[:20]}...")


async def fetch_all_models_from_api() -> List[dict]:
    """Fetch all available models from Ollama API tags endpoint"""
    print(f"\nFetching model list from {OLLAMA_TAGS_URL}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(OLLAMA_TAGS_URL)
        response.raise_for_status()
        data = response.json()
        models = data.get("models", [])
        print(f"Found {len(models)} total models from API")
        return models


def is_likely_cloud_model(name: str) -> bool:
    """
    Determine if a model name indicates it's a cloud model.
    Cloud models typically have:
    - Slash format (e.g., google/gemma, meta-llama/llama)
    - Known cloud provider prefixes (gemma, glm, minimax, gpt-oss, etc.)
    - Don't have the typical local format with digest
    """
    if not name:
        return False
    
    # Skip if contains digest hash (local models often have : followed by hash)
    if name.count(":") >= 2:  # e.g., "model:tag:sha256..."
        return False
    
    # Models with slash are definitely cloud (namespace format)
    if "/" in name:
        return True
    
    # Known cloud-only model families
    cloud_indicators = [
        "gemma3", "gemma4", "gemma-", "glm-", "glm4", "glmplus",
        "ministral", "ministral-",
        "minimax", "minimax-",
        "gpt-oss", "gpt-",
        "openthinker", "openthinker-",
        "qwq", "qwq-",
        "deepseek-llm", "deepseek-coder", "deepseek-",
        "mistral-ai/", "mistral-",
        "codestral", "codestral-",
        "phi4", "phi-4", "phi-",
        "claude", "claude-",
        "llama3.3", "llama-3.3", "llama-",
        "command-",
        "cohere-",
    ]
    
    name_lower = name.lower()
    return any(indicator.lower() in name_lower for indicator in cloud_indicators)


def extract_model_names(models_data: List[dict]) -> List[str]:
    """Extract and filter cloud model names"""
    all_names = [m.get("name", "") for m in models_data if m.get("name")]
    cloud_models = [n for n in all_names if is_likely_cloud_model(n)]
    return sorted(set(cloud_models))  # Deduplicate and sort


async def test_model(model_name: str) -> Tuple[bool, str]:
    """
    Test if a model is accessible.
    Returns (success, error_message)
    """
    class SimpleResponse(BaseModel):
        text: str

    try:
        agent = Agent(
            model=OllamaModel(
                model_name,
                provider=OllamaProvider(
                    base_url=OLLAMA_BASE_URL,
                    api_key=OLLAMA_API_KEY,
                ),
            ),
            output_type=SimpleResponse,
            instructions="Answer with exactly one word.",
        )
        
        result = await agent.run("Hi")
        return True, "OK"
    except Exception as e:
        error_msg = str(e)
        return False, error_msg


async def main():
    print("=" * 60)
    print("Ollama Cloud Models Accessibility Test")
    print("=" * 60)
    
    # Fetch models from API
    try:
        models_data = await fetch_all_models_from_api()
    except Exception as e:
        print(f"Error fetching models: {e}")
        sys.exit(1)
    
    # Filter cloud models
    cloud_models = extract_model_names(models_data)
    print(f"\nIdentified {len(cloud_models)} cloud models to test")
    
    if len(cloud_models) == 0:
        print("No cloud models identified! Showing all models that were found:")
        for m in models_data[:20]:
            print(f"   - {m.get('name', 'unknown')}")
        sys.exit(0)
    
    # Test models (limit concurrency)
    print("\nTesting models...")
    print("-" * 60)
    
    working = []
    failed = []
    error_categories = {}
    
    semaphore = asyncio.Semaphore(5)  # 5 concurrent requests
    
    async def test_with_limit(name):
        async with semaphore:
            return await test_model(name)
    
    tasks = [test_with_limit(name) for name in cloud_models]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for model, result in zip(cloud_models, results):
        if isinstance(result, Exception):
            success = False
            error = str(result)
        else:
            success, error = result
        
        if success:
            working.append(model)
            status = "✅ ACCESSIBLE"
        else:
            failed.append(model)
            # Categorize error
            error_lower = error.lower()
            if "subscription" in error_lower:
                category = "subscription required"
            elif "403" in error or "forbidden" in error_lower:
                category = "forbidden"
            elif "404" in error or "not found" in error_lower:
                category = "not found"
            elif "401" in error or "unauthorized" in error_lower:
                category = "unauthorized"
            elif "rate" in error_lower and "limit" in error_lower:
                category = "rate limited"
            else:
                category = f"other ({error[:40]})"
            
            error_categories[category] = error_categories.get(category, 0) + 1
            status = f"❌ {category}"
        
        print(f"{status:30s} {model}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tested: {len(cloud_models)}")
    print(f"✅ Accessible (free): {len(working)} ({len(working)/len(cloud_models)*100:.1f}%)")
    print(f"❌ Not accessible: {len(failed)} ({len(failed)/len(cloud_models)*100:.1f}%)")
    
    if error_categories:
        print("\nError breakdown:")
        for cat, count in sorted(error_categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")
    
    # Save results
    output = {
        "accessible": working,
        "not_accessible": failed,
        "error_breakdown": error_categories,
        "total_tested": len(cloud_models),
    }
    
    filename = "ollama_cloud_accessible_models.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ Results saved to: {filename}")
    
    # Also print just the accessible models clearly
    print("\n" + "=" * 60)
    print("ACCESSIBLE MODELS (free plan):")
    print("=" * 60)
    if working:
        for model in working:
            print(f"  • {model}")
    else:
        print("  (none found)")
    
    print("\n" + "=" * 60)
    print("NOT ACCESSIBLE MODELS (requires paid access):")
    print("=" * 60)
    if failed:
        for model in failed[:30]:  # Show first 30
            print(f"  • {model}")
        if len(failed) > 30:
            print(f"  ... and {len(failed) - 30} more")
    else:
        print("  (none)")


if __name__ == "__main__":
    asyncio.run(main())
