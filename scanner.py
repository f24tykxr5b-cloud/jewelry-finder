"""
Active scanner: finds platforms with a Catawiki-like business model.
Searches DuckDuckGo in multiple languages, scrapes each result,
and scores similarity to Catawiki (0-100).
Free, no API keys needed.
"""

import time
import re
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# ── Cache ──────────────────────────────────────────────────────────────────────
SCAN_CACHE_FILE = Path("scan_cache.json")
SCAN_TTL_HOURS  = 24

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,de;q=0.7",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# ── Search queries — 20+ across 7 languages & angles ─────────────────────────
SEARCH_QUERIES = [
    # English — auction angles
    "curated online auction platform jewelry collectibles art",
    "online auction house similar catawiki sell jewelry antiques",
    "expert verified auction site fine jewelry art collectibles",
    "sell estate jewelry online auction platform commission",
    "peer to peer jewelry auction platform curated lots",
    "luxury consignment auction jewelry watches art online",
    "antique jewelry marketplace auction online sell",
    "inherited jewelry sell online auction expert appraisal",
    "online auction platform collectibles jewelry europe",
    "fine art jewelry auction house online international bidding",
    # French
    "vente aux enchères en ligne bijoux antiquités expert commissaire",
    "plateforme enchères bijoux expertisés vendre en ligne",
    # German
    "online auktionshaus schmuck antiquitäten experten kuratiert",
    "schmuck versteigern online plattform experten geprüft",
    # Italian
    "aste online gioielli antiquariato esperti vendere",
    # Spanish
    "subasta joyas online plataforma expertos vender",
    "venta joyas antiguas subasta online comisión",
    # Dutch / Belgian
    "online veilinghuis sieraden kunst antiek Europa gecertificeerd",
    # Swedish / Nordic
    "online auktion smycken antikviteter sälj europa",
    # Polish
    "aukcja internetowa biżuteria antyki eksperci sprzedaj",
]

# ── Scoring signals ────────────────────────────────────────────────────────────
AUCTION_WORDS = [
    "auction", "bid", "lot", "hammer", "gavel", "enchère", "adjugé",
    "veiling", "bod", "auktion", "gebot", "subasta", "asta", "leilão",
]
CURATION_WORDS = [
    "curated", "expert", "verified", "specialist", "appraised", "authenticated",
    "commissaire", "expertise", "geprüft", "experte", "gecertificeerd",
]
JEWELRY_WORDS = [
    "jewelry", "jewellery", "jewels", "bijoux", "sieraden", "schmuck",
    "diamond", "ring", "necklace", "bracelet", "watch", "gemstone",
    "gold", "silver", "platinum", "estate jewelry",
]
COLLECTIBLE_WORDS = [
    "collectibles", "antiques", "art", "vintage", "rare", "coins",
    "antiquités", "kunst", "antiquiteiten", "uhren",
]
FEES_WORDS = [
    "buyer's premium", "seller fee", "commission", "frais", "provision",
    "käuferprovision", "kosten",
]
BLACKLIST_DOMAINS = {
    "google", "youtube", "facebook", "instagram", "twitter", "reddit",
    "wikipedia", "amazon", "alibaba", "etsy", "ebay", "pinterest",
    "forbes", "businessinsider", "bloomberg", "nytimes", "theguardian",
    "shopify", "wix", "wordpress", "medium", "linkedin", "tiktok",
}

# Domains we already track (populated at runtime)
KNOWN_DOMAINS: set = set()


# ── Helpers ────────────────────────────────────────────────────────────────────
def _domain(url: str) -> Optional[str]:
    try:
        h = urlparse(url).netloc.lower().replace("www.", "")
        return h if "." in h else None
    except Exception:
        return None


def _is_candidate(domain: str) -> bool:
    if not domain or len(domain) < 4:
        return False
    if domain in KNOWN_DOMAINS:
        return False
    if any(b in domain for b in BLACKLIST_DOMAINS):
        return False
    return True


def _count_signals(text: str, words: list) -> int:
    t = text.lower()
    return sum(1 for w in words if w in t)


def _score_page(text: str, title: str, description: str) -> dict:
    """
    Score a page's similarity to Catawiki's model.
    Returns score (0-100) and breakdown.
    """
    combined = (text + " " + title + " " + description).lower()

    auction_hits     = _count_signals(combined, AUCTION_WORDS)
    curation_hits    = _count_signals(combined, CURATION_WORDS)
    jewelry_hits     = _count_signals(combined, JEWELRY_WORDS)
    collectible_hits = _count_signals(combined, COLLECTIBLE_WORDS)
    fees_hits        = _count_signals(combined, FEES_WORDS)

    # Weighted score
    score = min(100, (
        min(auction_hits,     4) * 12 +   # max 48
        min(curation_hits,    3) * 10 +   # max 30
        min(jewelry_hits,     3) *  5 +   # max 15
        min(collectible_hits, 3) *  3 +   # max  9
        min(fees_hits,        2) *  4     # max  8
    ))

    return {
        "score":       score,
        "auction":     auction_hits,
        "curation":    curation_hits,
        "jewelry":     jewelry_hits,
        "collectible": collectible_hits,
        "fees":        fees_hits,
    }


def _scrape_site(url: str, timeout: int = 8) -> dict:
    """Fetches the homepage and extracts title, description, and body text."""
    result = {"title": "", "description": "", "text": "", "error": None}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            result["error"] = f"HTTP {r.status_code}"
            return result

        soup = BeautifulSoup(r.text, "lxml")

        result["title"] = soup.title.string.strip() if soup.title else ""

        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if meta_desc:
            result["description"] = meta_desc.get("content", "")[:300]

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        result["text"] = soup.get_text(" ", strip=True)[:3000]

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)[:60]

    return result


# ── Main scanner ───────────────────────────────────────────────────────────────
def run_scan(
    known_domains: set,
    min_score:     int   = 35,
    max_results:   int   = 12,
    progress_cb          = None,
) -> list:
    """
    Searches, scrapes, and scores platforms similar to Catawiki.

    Args:
        known_domains: domains already in our database (skip these)
        min_score:     minimum similarity score to include
        max_results:   cap on returned results
        progress_cb:   optional callable(current, total, message) for UI progress

    Returns:
        List of dicts sorted by score desc.
    """
    global KNOWN_DOMAINS
    KNOWN_DOMAINS = known_domains

    # ── Step 1: collect candidate URLs via DuckDuckGo ──────────────────────────
    candidates = {}  # domain → {url, title, description}

    with DDGS() as ddgs:
        for qi, query in enumerate(SEARCH_QUERIES):
            if progress_cb:
                progress_cb(qi, len(SEARCH_QUERIES) * 2, f"מחפש: {query[:45]}...")
            try:
                for r in ddgs.text(query, max_results=6):
                    d = _domain(r.get("href", ""))
                    if d and _is_candidate(d) and d not in candidates:
                        candidates[d] = {
                            "domain":      d,
                            "url":         r.get("href", f"https://{d}"),
                            "title":       r.get("title", d),
                            "description": r.get("body", "")[:200],
                        }
            except Exception:
                pass
            time.sleep(0.6)

    # ── Step 2: scrape & score each candidate ─────────────────────────────────
    results = []
    domains_list = list(candidates.keys())

    for ci, domain in enumerate(domains_list):
        info = candidates[domain]
        if progress_cb:
            msg = f"סורק: {domain}"
            progress_cb(
                len(SEARCH_QUERIES) + ci,
                len(SEARCH_QUERIES) + len(domains_list),
                msg,
            )

        scrape = _scrape_site(f"https://{domain}")
        scoring = _score_page(
            scrape["text"],
            scrape["title"] or info["title"],
            scrape["description"] or info["description"],
        )

        if scoring["score"] >= min_score:
            results.append({
                "domain":      domain,
                "url":         info["url"],
                "title":       scrape["title"] or info["title"],
                "description": scrape["description"] or info["description"],
                "score":       scoring["score"],
                "signals": {
                    "מכרזים 🔨":   scoring["auction"],
                    "אוצנות 🎯":   scoring["curation"],
                    "תכשיטים 💎":  scoring["jewelry"],
                    "אספנות 🏺":   scoring["collectible"],
                    "עמלות 💰":    scoring["fees"],
                },
                "scrape_error": scrape["error"],
            })

        time.sleep(0.4)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


# ── Cache helpers ──────────────────────────────────────────────────────────────
def load_scan_cache() -> Optional[list]:
    if SCAN_CACHE_FILE.exists():
        try:
            raw = json.loads(SCAN_CACHE_FILE.read_text(encoding="utf-8"))
            age_h = (time.time() - raw.get("_ts", 0)) / 3600
            if age_h < SCAN_TTL_HOURS:
                return raw.get("results", [])
        except Exception:
            pass
    return None


def save_scan_cache(results: list):
    SCAN_CACHE_FILE.write_text(
        json.dumps({"_ts": time.time(), "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
