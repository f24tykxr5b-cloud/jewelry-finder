"""
Discovers new jewelry/auction platforms via DuckDuckGo search.
No API key needed — completely free.
"""

import re
import time
from typing import Optional, List, Dict, Set
from urllib.parse import urlparse
from duckduckgo_search import DDGS

KNOWN_DOMAINS: Set[str] = set()  # populated at runtime from platforms_data

SEARCH_QUERIES = [
    "catawiki alternatives jewelry selling platform",
    "best online auction sites sell jewelry 2024",
    "marketplace sell fine jewelry antique online",
    "sell jewelry online auction platform europe",
    "online jewelry marketplace high traffic",
]

BLACKLIST = {
    "google", "youtube", "facebook", "instagram", "twitter", "pinterest",
    "reddit", "wikipedia", "amazon", "aliexpress", "shopify", "wix",
    "wordpress", "etsy.com/blog", "forbes", "businessinsider", "nytimes",
}


def _extract_domain(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return host if "." in host else None
    except Exception:
        return None


def _is_candidate(domain: str, known: set) -> bool:
    if not domain:
        return False
    if domain in known:
        return False
    if any(b in domain for b in BLACKLIST):
        return False
    return True


def search_new_platforms(known_domains: Set[str], max_results: int = 5) -> List[Dict]:
    """
    Searches DuckDuckGo for Catawiki-like platforms not already in our list.
    Returns list of dicts: {domain, title, description, url}
    """
    global KNOWN_DOMAINS
    KNOWN_DOMAINS = known_domains

    found = {}

    with DDGS() as ddgs:
        for query in SEARCH_QUERIES:
            try:
                results = ddgs.text(query, max_results=8)
                for r in results:
                    domain = _extract_domain(r.get("href", ""))
                    if _is_candidate(domain, known_domains) and domain not in found:
                        found[domain] = {
                            "domain": domain,
                            "title": r.get("title", domain),
                            "description": r.get("body", "")[:200],
                            "url": r.get("href", f"https://{domain}"),
                        }
                        if len(found) >= max_results * 2:
                            break
                time.sleep(0.8)
            except Exception:
                continue

    return list(found.values())[:max_results]
