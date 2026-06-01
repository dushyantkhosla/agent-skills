# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic-ai", "httpx"]
# ///

"""
Complete Ollama Cloud models accessibility test
Tests all models except those with digest hashes (local models)
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

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = "https://ollama.com/v1"
OLLAMA_TAGS_URL = "https://ollama.com/api/tags"

if not OLLAMA_API_KEY:
    print("ERROR: OLLAMA_API_KEY not found in environment")
    sys.exit(1)


async def fetch_all_models() -> List[str]:
    """Fetch all model names from API"""
    async with httpx.AsyncClient() as client:
        r = await client.get(OLLAMA_TAGS_URL)
        r.raise_for_status()
        data = r.json()
        models = data.get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]


def is_local_model(name: str) -> bool:
    """
    Detect if a model name indicates it's a local model.
    Local models often have digest hashes at the end (e.g., model:latest:sha256...)
    """
    # Count colons - cloud models typically have at most 1 colon (for tag)
    # Local models with digests have 2+ colons
    colon_count = name.count(":")
    if colon_count >= 2:
        return True
    return False


async def test_model(model_name: str) -> Tuple[bool, str]:
    """Test if a model is accessible"""
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
        return False, str(e)


async def main():
    print("Fetching all models from Ollama API...")
    all_models = await fetch_all_models()
    
    # Filter out local models (those with digest hashes)
    cloud_candidates = [m for m in all_models if not is_local_model(m)]
    
    print(f"\nTotal models from API: {len(all_models)}")
    print(f"After filtering local/digest models: {len(cloud_candidates)}")
    print(f"\nModels to test:\n  " + "\n  ".join(f"• {m}" for m in sorted(cloud_candidates)))
    
    print(f"\nTesting {len(cloud_candidates)} models...")
    print("-" * 60)
    
    working = []
    failed = []
    errors = {}
    
    semaphore = asyncio.Semaphore(5)
    
    async def test_limited(name):
        async with semaphore:
            return await test_model(name)
    
    tasks = [test_limited(m) for m in cloud_candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for model, result in zip(cloud_candidates, results):
        if isinstance(result, Exception):
            success, error = False, str(result)
        else:
            success, error = result
        
        if success:
            working.append(model)
            status = "✅ ACCESSIBLE"
        else:
            failed.append(model)
            err_lower = error.lower()
            if "subscription" in err_lower:
                cat = "subscription required"
            elif "403" in err_lower or "forbidden" in err_lower:
                cat = "forbidden"
            elif "404" in err_lower or "not found" in err_lower:
                cat = "not found"
            elif "401" in err_lower or "unauthorized" in err_lower:
                cat = "unauthorized"
            elif "rate" in err_lower and "limit" in err_lower:
                cat = "rate limited"
            elif "event loop" in err_lower or "retries" in err_lower:
                cat = f"rate/timeout: {error[:30]}"
            else:
                cat = f"other: {error[:40]}"
            errors[cat] = errors.get(cat, 0) + 1
            status = f"❌ {cat}"
        
        print(f"{status:35s} {model}")
    
    # Save results
    output = {
        "accessible": working,
        "not_accessible": failed,
        "error_breakdown": errors,
        "total_tested": len(cloud_candidates),
    }
    
    with open("ollama_all_cloud_models.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n✅ ACCESSIBLE (free) - {len(working)} models:")
    for m in working:
        print(f"   • {m}")
    
    print(f"\n❌ NOT ACCESSIBLE - {len(failed)} models:")
    for m in failed:
        print(f"   • {m}")
    
    print("\nError breakdown:")
    for cat, cnt in sorted(errors.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")
    
    print(f"\nResults saved to: ollama_all_cloud_models.json")


if __name__ == "__main__":
    asyncio.run(main())
