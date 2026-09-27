# INBOX (Claude → agent). Newest entry at the bottom.

## I-001 · 2026-09-27T04:16:43+05:30
Start with AGENT_BRIEF.md, M1. Work autonomously through all milestones.

## I-002 · 2026-09-27T12:44:58+05:30
New work (v3), after reading AGENT_BRIEF.md + docs/ROADMAP.md: the project already exists and is at v2 (built by Claude; see README.md, git log). Your job now: (1) website candidate discovery for companies with no registry homepage and no usable e-mail domain: probe <legal-name-tokens>.no / .com (max 3 probes per company, polite) and publish ONLY through the existing exact-identity gate; measure on data/live/entry-companies.jsonl (first 200) and report the gain. (2) dated activity from news/nyheter/aktuelt pages on verified sites (<time datetime> or clear dates), same evidence rules as activity.py. (3) keep all tests green (uv run --with pytest pytest -q), add tests, commit each step, report per PROTOCOL.md. Never push or submit.
