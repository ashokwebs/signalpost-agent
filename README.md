# Signalpost entry: exact-company research agent for Norwegian companies

Built on the Builderr **Signalpost reference agent** (unmodified baseline preserved in the first commit and in
`README-REFERENCE.md`), with changes that raise coverage without weakening the exact-identity gates.

## One command

```bash
uv sync
uv run python scripts/run_competition_batch.py \
  --organisations <batch.jsonl> --bulk <brreg-enheter.csv.gz> \
  --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json \
  --run-id <id> --expected-count 100
```

`<batch.jsonl>` is one `{"organisation_number": "..."}` per line (the evaluator's file). `<brreg-enheter.csv.gz>` is the
Brønnøysund bulk download (`https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv`), passed as downloaded (gzip).
Exactly one terminal envelope per input, always.

## What changed vs the reference agent

| Change | Why | Measured effect |
|---|---|---|
| **Backoff on 429/502/503/504** (honours `Retry-After`, 2s→4s→8s, 4 attempts) and **paced Regnskapsregisteret calls** (≥0.6s between starts) | Cold runs got HTTP 503 from the accounts API on bursts | Financials available: **4/10 → 10/10** on the smoke set; **924/1,000** in the submitted run (75 records return HTTP 503 persistently at source) |
| **Website candidates from the registry e-mail domain** when no homepage is registered (free-mail/ISP domains excluded) | Many companies register `post@company.no` but no website | Websites **1/10 → 3/10** on the smoke set. Every candidate passes the *same* exact-identity gate |
| **Org-number mentions on any same-domain page** (raw visible text incl. footers, verbatim span kept) accepted as exact identity | Footers carry "Org.nr 924 367 555" but readability extraction drops them | +4 of 76 previously gated sites, zero wrong-company risk (exact 9-digit match) |
| **Dated activity from the verified site's own RSS/Atom feed** (v2) | "Dated public activity" is a scored family; the reference batch emitted none | Only for exact-identity sites; undated items dropped; `not_applicable` / `not_found` states kept honest |
| **Hiring from NAV's official job feed** (v2, `--nav-index`) | Hiring is a scored family; NAV ad details carry the employer org number | Published only on exact org-number match; recruiter-on-behalf ads flagged; index built by `scripts/nav_feed_index.py` (declared cache) |
| **Live Enhetsregisteret fallback** for organisations absent from the bulk snapshot | The reference runner raised and emitted nothing for the whole batch | Batch no longer crashes; affected entities emit complete envelopes |

## Source policy (declared)

- Official: Enhetsregisteret bulk + entity API, Regnskapsregisteret (accounts and account-copy years), roles, subunits, group.
- Company-owned: the verified official website and pages on the same registered domain; social links published only when
  the handle passes the social identity gate.
- No search engines, no unofficial platform clients, no personal credentials, no third-party paid APIs.
  **Declared third-party cost: $0 per 100-company batch.**
- robots.txt respected; honest User-Agent; public-URL guard against private/internal addresses (reference implementation).

## Identity and abstention

Organisation number is the anchor. A website is published only when the organisation number appears on the site
(homepage or same-domain page) or all legal-name tokens appear together in homepage identity evidence. Otherwise the website
record stays `review`/`related_or_uncertain` and is not published. Missing values are never converted to zero.

## Artifacts

- `submission/profiles-1000.jsonl.gz` / `submission/envelopes-1000.jsonl.gz`: 1,000 completed profiles; manifest `submission/manifest-1000.txt`; coverage `submission/coverage-1000.json`
- `submission/run-report-1000.json`: runtime, requests (5,982 for 1,000 companies), validation checks (`zero_silent_drops`, terminal states)
- `docs/ROADMAP.md`: next versions (NAV job-feed hiring index, dated company-site activity)

Tests: `uv run --with pytest pytest -q` (104 passed, 5 subtests).
