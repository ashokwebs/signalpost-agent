import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from norway_company_agent.activity import activity_evidence, parse_feed  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Nyheter</title>
<item><title>Ny avdeling i Bergen</title><link>https://ex.no/nyheter/1</link><pubDate>Tue, 15 Sep 2026 10:00:00 +0200</pubDate></item>
<item><title>Uten dato</title><link>https://ex.no/nyheter/2</link></item>
<item><title>Eldre sak</title><link>https://ex.no/nyheter/0</link><pubDate>Mon, 01 Jun 2026 08:00:00 +0200</pubDate></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Lansering</title>
<link href="https://ex.no/a"/><updated>2026-09-20T12:00:00Z</updated></entry></feed>"""


def test_parse_rss_keeps_only_dated_items_newest_first():
    items = parse_feed(RSS)
    assert [i["title"] for i in items] == ["Ny avdeling i Bergen", "Eldre sak"]
    assert items[0]["published"] == "2026-09-15T08:00:00Z"


def test_parse_atom():
    assert parse_feed(ATOM)[0]["title"] == "Lansering"


def _profile(publishable=True, feeds=("https://ex.no/feed",)):
    return {"evidence": {"website": {"status": "available", "source_url": "https://ex.no/",
            "value": {"final_url": "https://ex.no/", "feed_links": list(feeds), "identity_assessment": {"publishable": publishable}}}}}


def test_activity_only_for_exact_sites_and_counts_requests():
    ev, n = activity_evidence(_profile(publishable=False))
    assert ev["status"] == "not_applicable" and n == 0
    ev, n = activity_evidence(_profile(), fetch=lambda url: (RSS, 200))
    assert ev["status"] == "available" and n == 1 and ev["value"]["items"][0]["feed_url"] == "https://ex.no/feed"
    ev, n = activity_evidence(_profile(feeds=()))
    assert ev["status"] == "not_found" and n == 0
