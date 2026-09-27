"""Dated public activity from the verified company website's own RSS/Atom feed or news/nyheter/aktuelt pages.

Only runs for websites that passed the exact-identity gate. Each item keeps its title, link, publication date, the source URL,
retrieval time and the content hash. Items without a parseable date are dropped (activity must be dated).
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from bs4 import BeautifulSoup

from .evidence import evidence, utc_now

UA = "signalpost-entrant/1.0 (company research; contact via builderr.ai)"
ATOM = "{http://www.w3.org/2005/Atom}"
NEWS_PATH = re.compile(r"/(?:news|press|aktuelt|nyheter|artikler|blog)(?:/|$)", re.I)

MONTHS = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    # 1. Standard email / ISO formats
    for parse in (parsedate_to_datetime, lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))):
        try:
            d = parse(text)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, IndexError):
            continue
    # 2. Date only: YYYY-MM-DD
    m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", text)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            return d.isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    # 3. Numeric European: DD.MM.YYYY
    m = re.search(r"\b(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.(20\d{2})\b", text)
    if m:
        try:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
            return d.isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    # 4. Textual month: DD. Month YYYY
    m = re.search(r"\b(0?[1-9]|[12]\d|3[01])\.?\s*([a-zA-ZæøåÆØÅ]+)\.?\s+(20\d{2})\b", text)
    if m:
        month = m.group(2).lower().rstrip(".")
        if month in MONTHS:
            try:
                d = datetime(int(m.group(3)), MONTHS[month], int(m.group(1)), tzinfo=timezone.utc)
                return d.isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
    return None


def parse_feed(raw: bytes, limit: int = 10) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    items: list[dict[str, Any]] = []
    for item in root.iter("item"):  # RSS 2.0
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": _date(item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")),
        })
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        link = entry.find(f"{ATOM}link")
        items.append({
            "title": (entry.findtext(f"{ATOM}title") or "").strip(),
            "link": (link.get("href") if link is not None else "") or "",
            "published": _date(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
        })
    dated = [i for i in items if i["published"] and i["title"]]
    dated.sort(key=lambda i: i["published"], reverse=True)
    return dated[:limit]


def parse_html_news(raw: bytes, base_url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Extract dated news items from an HTML page with <time datetime> or clear dates."""
    try:
        html = raw.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for el in soup.find_all(["article", "time"]):
        if el.name == "article":
            time_tag = el.find("time")
            date_val = _date(time_tag.get("datetime") if time_tag else None) or _date(time_tag.get_text() if time_tag else None)
            if not date_val:
                date_val = _date(el.get_text(" ", strip=True))
            if not date_val:
                continue
            a = el.find("a", href=True)
            h = el.find(["h1", "h2", "h3", "h4", "h5"])
            title = (h.get_text(strip=True) if h else (a.get_text(strip=True) if a else "")).strip()
            link = urllib.parse.urljoin(base_url, a["href"]) if a else base_url
            if title and date_val and link not in seen_links:
                seen_links.add(link)
                items.append({"title": title, "link": link, "published": date_val})
        elif el.name == "time":
            date_val = _date(el.get("datetime")) or _date(el.get_text())
            if not date_val:
                continue
            parent = el.find_parent(["article", "li", "div", "tr", "section"])
            if not parent:
                continue
            a = parent.find("a", href=True)
            h = parent.find(["h1", "h2", "h3", "h4", "h5"])
            title = (h.get_text(strip=True) if h else (a.get_text(strip=True) if a else "")).strip()
            link = urllib.parse.urljoin(base_url, a["href"]) if a else base_url
            if title and len(title) >= 4 and link not in seen_links:
                seen_links.add(link)
                items.append({"title": title, "link": link, "published": date_val})

    # If single article page and no items found yet
    if not items and NEWS_PATH.search(urllib.parse.urlparse(base_url).path):
        time_tag = soup.find("time")
        date_val = _date(time_tag.get("datetime") if time_tag else None) or _date(time_tag.get_text() if time_tag else None)
        if not date_val:
            date_val = _date(soup.get_text(" ", strip=True)[:2000])
        h1 = soup.find(["h1", "h2"])
        title = (h1.get_text(strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "")).strip()
        if title and date_val:
            items.append({"title": title, "link": base_url, "published": date_val})

    dated = [i for i in items if i["published"] and i["title"]]
    dated.sort(key=lambda i: i["published"], reverse=True)
    return dated[:limit]


def _fetch(url: str) -> tuple[bytes | None, int]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/atom+xml,application/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(1_000_000), resp.status
    except Exception:
        return None, 0


def activity_evidence(profile: dict[str, Any], fetch: Callable[[str], tuple[bytes | None, int]] = _fetch) -> tuple[dict[str, Any], int]:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    if website.get("status") != "available" or not (value.get("identity_assessment") or {}).get("publishable"):
        return evidence(
            "activity",
            "not_applicable",
            "company_site_feed",
            website.get("source_url") or "",
            note="No exact-identity website to read activity from",
        ), 0

    requests = 0

    # 1. Try RSS/Atom feeds first
    feeds = value.get("feed_links") or []
    for url in feeds:
        raw, status = fetch(url)
        requests += 1
        if not raw:
            continue
        items = parse_feed(raw)
        if items:
            digest = hashlib.sha256(raw).hexdigest()
            for it in items:
                it.update({"feed_url": url, "page_url": url, "retrieved_at": utc_now(), "content_sha256": digest})
            return evidence(
                "activity",
                "available",
                "company_site_feed",
                url,
                value={"items": items},
                content_sha256=digest,
                effective_at=items[0]["published"],
            ), requests

    # 2. Try news/nyheter/aktuelt HTML pages on verified site
    news_urls: list[str] = list(value.get("news_links") or [])
    for page in value.get("pages") or []:
        p_url = page.get("url") or ""
        if NEWS_PATH.search(urllib.parse.urlparse(p_url).path) and p_url not in news_urls:
            news_urls.append(p_url)

    for url in news_urls:
        raw, status = fetch(url)
        requests += 1
        if not raw:
            continue
        items = parse_html_news(raw, url)
        if items:
            digest = hashlib.sha256(raw).hexdigest()
            for it in items:
                it.update({"feed_url": url, "page_url": url, "retrieved_at": utc_now(), "content_sha256": digest})
            return evidence(
                "activity",
                "available",
                "company_site_news",
                url,
                value={"items": items},
                content_sha256=digest,
                effective_at=items[0]["published"],
            ), requests

    # 3. Neither feed nor news page yielded dated items
    if feeds:
        note = "Feed had no dated items"
        fallback_url = feeds[0]
    elif news_urls:
        note = "News pages had no dated items"
        fallback_url = news_urls[0]
    else:
        note = "Verified website advertises no RSS/Atom feed"
        fallback_url = value.get("final_url") or ""

    return evidence("activity", "not_found", "company_site_feed", fallback_url, note=note), requests
