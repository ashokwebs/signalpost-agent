"""Dated public activity from the verified company website's own RSS/Atom feed.

Only runs for websites that passed the exact-identity gate. Each item keeps its title, link, publication date, the feed URL,
retrieval time and the feed's content hash. Items without a parseable date are dropped (activity must be dated).
"""
from __future__ import annotations

import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from .evidence import evidence, utc_now

UA = "signalpost-entrant/1.0 (company research; contact via builderr.ai)"
ATOM = "{http://www.w3.org/2005/Atom}"


def _date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    for parse in (parsedate_to_datetime, lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))):
        try:
            d = parse(text)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, IndexError):
            continue
    return None


def parse_feed(raw: bytes, limit: int = 10) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    items: list[dict[str, Any]] = []
    for item in root.iter("item"):  # RSS 2.0
        items.append({"title": (item.findtext("title") or "").strip(), "link": (item.findtext("link") or "").strip(),
                      "published": _date(item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date"))})
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        link = entry.find(f"{ATOM}link")
        items.append({"title": (entry.findtext(f"{ATOM}title") or "").strip(),
                      "link": (link.get("href") if link is not None else "") or "",
                      "published": _date(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated"))})
    dated = [i for i in items if i["published"] and i["title"]]
    dated.sort(key=lambda i: i["published"], reverse=True)
    return dated[:limit]


def _fetch(url: str) -> tuple[bytes | None, int]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(1_000_000), resp.status
    except Exception:
        return None, 0


def activity_evidence(profile: dict[str, Any], fetch: Callable[[str], tuple[bytes | None, int]] = _fetch) -> tuple[dict[str, Any], int]:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    if website.get("status") != "available" or not (value.get("identity_assessment") or {}).get("publishable"):
        return evidence("activity", "not_applicable", "company_site_feed", website.get("source_url") or "",
                        note="No exact-identity website to read activity from"), 0
    feeds = value.get("feed_links") or []
    if not feeds:
        return evidence("activity", "not_found", "company_site_feed", value.get("final_url") or "",
                        note="Verified website advertises no RSS/Atom feed"), 0
    requests = 0
    for url in feeds:
        raw, status = fetch(url)
        requests += 1
        if not raw:
            continue
        items = parse_feed(raw)
        if items:
            digest = hashlib.sha256(raw).hexdigest()
            for it in items:
                it.update({"feed_url": url, "retrieved_at": utc_now(), "content_sha256": digest})
            return evidence("activity", "available", "company_site_feed", url, value={"items": items},
                            content_sha256=digest, effective_at=items[0]["published"]), requests
    return evidence("activity", "not_found", "company_site_feed", feeds[0], note="Feed had no dated items"), requests
