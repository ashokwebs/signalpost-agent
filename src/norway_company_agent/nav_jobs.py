"""Hiring evidence from NAV's official job-vacancy feed (pam-stilling-feed.nav.no).

Identity rule: an ad is published for a company only when the ad detail's `employer.orgnr` equals the company's
organisation number. Employer names are used only to generate candidates (no name-only publication). The org number in an
ad identifies the *advertiser*; when the ad text says another party is recruiting on someone's behalf, that is flagged.

Evidence per ad: detail URL, public ad link, published/expires/updated dates, retrieval time and content hash.
A checked index with zero matches yields `not_found` (checked, none), which is different from `not_fetched`.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .evidence import evidence, utc_now
from .identity import _tokens

BASE = "https://pam-stilling-feed.nav.no"
UA = "signalpost-entrant/1.0 (company research; contact via builderr.ai)"
RECRUITER_HINT = re.compile(r"(på vegne av|on behalf of|håndterer rekrutteringen|rekrutterer for|står som annonsør|bemanningsbyrå)", re.I)


def load_index(path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(path)
    return json.loads(p.read_text()) if p.is_file() else {}


def name_key(name: str | None) -> str:
    return " ".join(sorted(set(_tokens(name))))


def active_by_name(index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for uuid, row in index.items():
        if row.get("s") == "ACTIVE" and row.get("b"):
            table.setdefault(name_key(row["b"]), []).append(uuid)
    return table


def _public_token() -> str:
    raw = urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/publicToken", headers={"User-Agent": UA}), timeout=30).read().decode()
    match = re.search(r"(eyJ[\w-]+\.[\w-]+\.[\w-]+)", raw)
    if not match:
        raise RuntimeError("NAV public token not found")
    return match.group(1)


class NavDetailFetcher:
    """Fetches ad detail entries with NAV's published public token (fetched once per run, never stored)."""

    def __init__(self) -> None:
        self._token: str | None = None
        self.requests = 0

    def __call__(self, uuid: str) -> tuple[dict[str, Any] | None, str | None, str]:
        if self._token is None:
            self._token = _public_token()
            self.requests += 1
        url = f"{BASE}/api/v1/feedentry/{uuid}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json", "User-Agent": UA})
        self.requests += 1
        try:
            raw = urllib.request.urlopen(req, timeout=30).read()
            return json.loads(raw), hashlib.sha256(raw).hexdigest(), url
        except Exception:
            return None, None, url


def job_evidence(profile: dict[str, Any], by_name: dict[str, list[str]], fetch: Callable[[str], tuple[dict | None, str | None, str]],
                 max_details: int = 5) -> dict[str, Any]:
    org = str(profile.get("organisation_number"))
    key = name_key(profile.get("name"))
    candidates = by_name.get(key, [])[:max_details] if key else []
    postings = []
    for uuid in candidates:
        detail, digest, url = fetch(uuid)
        ad = (detail or {}).get("ad_content") or {}
        employer = ad.get("employer") or {}
        if str(employer.get("orgnr") or "") != org:
            continue  # candidate by name only: not published
        description = str(employer.get("description") or "") + " " + str(ad.get("description") or "")
        postings.append({
            "title": ad.get("title"),
            "link": ad.get("link") or f"https://arbeidsplassen.nav.no/stillinger/stilling/{uuid}",
            "source_url": url,
            "published": ad.get("published"),
            "expires": ad.get("expires"),
            "updated": ad.get("updated"),
            "work_locations": [{k: loc.get(k) for k in ("municipal", "county", "city")} for loc in ad.get("workLocations") or []],
            "advertiser_orgnr": org,
            "relationship": "advertiser",
            "recruiting_on_behalf_flag": bool(RECRUITER_HINT.search(description)),
            "content_sha256": digest,
            "retrieved_at": utc_now(),
        })
    source = f"{BASE}/api/v1/feed"
    if postings:
        return evidence("jobs", "available", "official_job_feed_nav", source, value={"postings": postings, "candidates_checked": len(candidates)},
                        note="Employer org number in NAV ad detail equals the company's organisation number")
    return evidence("jobs", "not_found", "official_job_feed_nav", source, value={"postings": [], "candidates_checked": len(candidates)},
                    note="Checked NAV active-ad index: no ad whose employer org number matches")
