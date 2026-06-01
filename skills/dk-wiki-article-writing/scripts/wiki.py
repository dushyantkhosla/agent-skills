# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pywikibot>=9.0",
#     "mwparserfromhell>=0.6",
# ]
# ///
"""Fetch Wikipedia article text, references, and table of contents.
Usage: uv run wiki.py "Article Title" [--refs] [--toc] [--full] [--chars N]
"""
import os, sys, re, argparse

os.environ['PYWIKIBOT_NO_USER_CONFIG'] = '1'

def main():
    parser = argparse.ArgumentParser(description='Fetch Wikipedia article')
    parser.add_argument('title', help='Wikipedia article title')
    parser.add_argument('--refs', action='store_true', help='Extract URLs from references')
    parser.add_argument('--toc', action='store_true', help='Extract table of contents links')
    parser.add_argument('--full', action='store_true', help='Print full article text')
    parser.add_argument('--chars', type=int, default=5000, help='Characters to print (default 5000)')
    args = parser.parse_args()

    import pywikibot

    site = pywikibot.Site('en', 'wikipedia')
    page = pywikibot.Page(site, args.title)

    if not page.exists():
        print(f"No Wikipedia article found for: {args.title}")
        sys.exit(0)

    text = page.text
    print(f"# Wikipedia: {page.title()}")
    print(f"# Length: {len(text)} chars")
    print(f"# URL: https://en.wikipedia.org/wiki/{page.title().replace(' ', '_')}")
    print()

    if args.full:
        print(text)
    else:
        print(text[:args.chars])
        if len(text) > args.chars:
            print(f"\n... [{len(text) - args.chars} more chars]")

    if args.refs:
        urls = re.findall(r'https?://[^\s\]<"]+', text)
        unique_urls = list(dict.fromkeys(urls))
        print(f"\n--- References ({len(unique_urls)} URLs) ---")
        for url in unique_urls[:30]:
            print(url)

    if args.toc:
        links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', text[:3000])
        print(f"\n--- Table of Contents ({len(links)} links) ---")
        for link in links[:20]:
            print(link)

if __name__ == '__main__':
    main()
