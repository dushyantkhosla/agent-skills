# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27",
# ]
# ///
"""Web search via Brave Search API. Only dependency: BRAVE_API_KEY env var.
Usage: uv run search.py "query" [-n NUM] [--freshness pw] [--content]
"""
import os, sys, json, argparse
from urllib.parse import quote_plus

def search_brave(query: str, num: int = 10, freshness: str | None = None, country: str = "US") -> list[dict]:
    import httpx
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        print("ERROR: BRAVE_API_KEY not set. Get one at https://api-dashboard.search.brave.com/register", file=sys.stderr)
        sys.exit(1)

    params = {"q": query, "count": min(num, 20), "search_lang": "en", "country": country}
    if freshness:
        params["freshness"] = freshness

    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("web", {}).get("results", [])

def extract_content(url: str) -> str:
    """Fetch URL and extract readable text via Brave's summarizer endpoint or fallback to raw fetch."""
    import httpx
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return _fallback_fetch(url)

    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": url, "count": 1},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        if results and results[0].get("description"):
            return results[0]["description"]
    except Exception:
        pass
    return _fallback_fetch(url)

def _fallback_fetch(url: str) -> str:
    import httpx
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Basic HTML to text: strip tags
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:8000]
    except Exception as e:
        return f"[Failed to fetch: {e}]"

def main():
    parser = argparse.ArgumentParser(description="Web search via Brave Search API")
    parser.add_argument("query", help="Search query")
    parser.add_argument("-n", type=int, default=10, help="Number of results (default 10)")
    parser.add_argument("--freshness", help="Time filter: pd, pw, pm, py, or date range")
    parser.add_argument("--country", default="US", help="Country code (default US)")
    parser.add_argument("--content", action="store_true", help="Fetch page content for each result")
    args = parser.parse_args()

    results = search_brave(args.query, args.n, args.freshness, args.country)

    if not results:
        print("No results found.")
        sys.exit(0)

    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        age = r.get("age", "")
        snippet = r.get("description", "")

        print(f"--- Result {i} ---")
        print(f"Title: {title}")
        print(f"Link: {url}")
        if age:
            print(f"Age: {age}")
        print(f"Snippet: {snippet}")

        if args.content:
            content = extract_content(url)
            print(f"Content:\n{content}")

        print()

if __name__ == "__main__":
    main()
