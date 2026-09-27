# Signalpost: improvement roadmap (revisions allowed until 18 Oct 2026, 5 versions total)

## v1 (27 Sep)
- 503/429 backoff with Retry-After + paced Regnskapsregisteret calls → financials 4/10 → 10/10 on the cold smoke set
- Website candidates from the registry e-mail domain (non-free-mail) → same exact-identity gate → websites 1/10 → 3/10
- Live Enhetsregisteret fallback for organisations missing from the bulk snapshot → no crash, no dropped envelope

## v2 (27–28 Sep, built; activates when the NAV index finishes building)
- **Hiring family via NAV's official job-vacancy feed** (pam-stilling-feed.nav.no, public token published by NAV).
  Entries carry businessName; detail entries carry the employer org number → exact match. Plan: offline index of ACTIVE ads
  keyed by org number (declared cache), incremental refresh from the stored cursor at run time; publish only org-number matches.
- Company-site activity: dated news/press pages + RSS/Atom feeds on verified sites (evidence: page URL + date + hash).
- Company-owned social profiles linked from the verified site (already extracted; ensure they're published with evidence).

## v3
- Candidate generation for sites without registry e-mail: <legal-name-tokens>.no / .com probes, gated identically.
- Measurement loop on dev/validation splits (no host overlap), false-change rate on repeated refresh.
