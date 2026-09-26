"""Build/refresh a compact local index of NAV's public job-vacancy feed (pam-stilling-feed.nav.no).

The feed is NAV's official publication feed for downstream consumers; NAV publishes the public token at /api/publicToken.
We page forward from the stored cursor (first run: from the beginning), politely, and keep one row per ad UUID with its latest
status, employer business name, municipality, title and modification time. Detail lookups (employer organisation number)
happen later, only for ACTIVE ads whose employer name matches a batch company, and only org-number matches are published.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://pam-stilling-feed.nav.no"
OUT = Path(__file__).resolve().parent.parent / "data" / "nav"
UA = "signalpost-entrant/1.0 (company research; contact via builderr.ai)"


def token() -> str:
    raw = urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/publicToken", headers={"User-Agent": UA}), timeout=30).read().decode()
    return re.search(r"(eyJ[\w-]+\.[\w-]+\.[\w-]+)", raw).group(1)


def main(max_pages: int = 5000, delay: float = 0.5) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index_path, cursor_path = OUT / "ads.json", OUT / "cursor.txt"
    ads = json.loads(index_path.read_text()) if index_path.exists() else {}
    url = cursor_path.read_text().strip() if cursor_path.exists() else "/api/v1/feed"
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/json", "User-Agent": UA}
    pages = 0
    while url and pages < max_pages:
        try:
            data = json.load(urllib.request.urlopen(urllib.request.Request(BASE + url, headers=headers), timeout=60))
        except Exception as exc:  # keep the cursor; next run resumes here
            print("stop:", type(exc).__name__, url, file=sys.stderr)
            break
        for item in data.get("items", []):
            e = item.get("_feed_entry") or {}
            ads[e.get("uuid") or item["id"]] = {"s": e.get("status"), "b": e.get("businessName"), "m": e.get("municipal"),
                                                "t": e.get("title"), "d": e.get("sistEndret") or item.get("date_modified")}
        pages += 1
        nxt = data.get("next_url")
        if not nxt or not data.get("items"):
            cursor_path.write_text(url)      # caught up: stay on the last page and re-read it next time
            break
        url = nxt
        cursor_path.write_text(url)
        if pages % 25 == 0:
            index_path.write_text(json.dumps(ads))
            print(f"{pages} pages, {len(ads)} ads, active {sum(1 for a in ads.values() if a['s'] == 'ACTIVE')}", file=sys.stderr)
        time.sleep(delay)
    index_path.write_text(json.dumps(ads))
    print(json.dumps({"pages": pages, "ads": len(ads), "active": sum(1 for a in ads.values() if a["s"] == "ACTIVE")}))


if __name__ == "__main__":
    main()
