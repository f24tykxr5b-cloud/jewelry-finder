"""
Fetches traffic data from SimilarWeb public pages.
Free – no API key needed.
"""

import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
}


def parse_traffic_number(text: str) -> str:
    """Normalize traffic strings like '12.3M', '456K' to readable format."""
    text = text.strip()
    return text


def fetch_similarweb_data(domain: str) -> dict:
    """
    Scrapes publicly available data from SimilarWeb for a given domain.
    Returns a dict with traffic stats or error info.
    """
    url = f"https://www.similarweb.com/website/{domain}/"
    result = {
        "monthly_visits": "לא זמין",
        "global_rank": "לא זמין",
        "country_rank": "לא זמין",
        "top_countries": [],
        "bounce_rate": "לא זמין",
        "pages_per_visit": "לא זמין",
        "avg_visit_duration": "לא זמין",
        "traffic_sources": {},
        "source_url": url,
        "error": None,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Monthly visits
        visits_el = soup.find("span", {"data-test": "total-visits"})
        if visits_el:
            result["monthly_visits"] = visits_el.get_text(strip=True)
        else:
            # Fallback: look for the engagement section
            for span in soup.find_all("p", class_=re.compile(r"engagement")):
                text = span.get_text(strip=True)
                if any(c in text for c in ["M", "K", "B"]) and "visit" in text.lower():
                    result["monthly_visits"] = text
                    break

        # Global rank
        rank_el = soup.find("span", {"data-test": "global-rank"})
        if rank_el:
            result["global_rank"] = rank_el.get_text(strip=True)

        # Try JSON-LD or meta tags as fallback
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and "aggregateRating" in data:
                    pass
            except Exception:
                pass

        # Bounce rate, pages/visit, duration from engagement overview
        engagement_items = soup.find_all("div", class_=re.compile(r"engagement-list__item|GeneralStats"))
        for item in engagement_items:
            label_el = item.find(class_=re.compile(r"label|title", re.I))
            value_el = item.find(class_=re.compile(r"value|number", re.I))
            if label_el and value_el:
                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                if "bounce" in label:
                    result["bounce_rate"] = value
                elif "pages" in label:
                    result["pages_per_visit"] = value
                elif "duration" in label or "time" in label:
                    result["avg_visit_duration"] = value

        # Top countries
        country_items = soup.find_all("span", class_=re.compile(r"country"))
        seen = []
        for el in country_items[:10]:
            t = el.get_text(strip=True)
            if t and t not in seen and len(t) > 1:
                seen.append(t)
        if seen:
            result["top_countries"] = seen[:5]

    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


def fetch_all_platforms(platforms: list, delay: float = 1.5) -> dict:
    """
    Fetches SimilarWeb data for all platforms.
    Returns dict keyed by domain.
    """
    results = {}
    for i, platform in enumerate(platforms):
        domain = platform["domain"]
        print(f"[{i+1}/{len(platforms)}] Fetching: {domain}...")
        results[domain] = fetch_similarweb_data(domain)
        if i < len(platforms) - 1:
            time.sleep(delay)
    return results
