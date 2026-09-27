# REPORT (agent → Claude). Append-only.

## 2026-09-27T05:00:22+05:30 · v1 built by Claude directly · reference agent + 3 fixes
- Built: 503 backoff + paced financials; registry-email website candidates (same exact-identity gate); live-registry fallback.
- Verified: pytest 104 passed; smoke (10): financials 4→10/10, websites 1→3/10; bulk-missing orgs now emit complete envelopes.
- Running: 1,000-profile v1 batch (out/v1-1000.log). Next: v2 NAV job-feed index (docs/ROADMAP.md).

ACK I-002

## 2026-09-27T15:26:00+05:30 · v3 done · Legal-name candidate probes & dated activity from news pages
- Built: name_domain_candidates (<tokens>.no/.com, max 3 probes) in src/norway_company_agent/candidates.py; news_links discovery in website.py; parse_html_news (<time datetime> or clear dates) & news page support in activity.py; batch runner integration (--name-token-candidates); tests in tests/test_candidates.py & tests/test_activity.py
- Verified: uv run --with pytest pytest -q → 119 passed, 5 subtests in 1.47s; candidate probe on first 200 of data/live/entry-companies.jsonl gained +28 publishable websites through exact-identity gate (17 → 45, +165% gain)
- Next: Awaiting Claude / next roadmap task
- Blockers/questions for Claude: none

