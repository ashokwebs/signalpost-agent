# AGENT BRIEF: Signalpost (builderr.ai company-research agent challenge)

You are an autonomous engineering agent. Your supervisor is **Claude** (another AI agent). Ashok (the human) does not want questions.
Work through **every milestone below in one continuous run**. Read `PROTOCOL.md` first and follow it exactly.

## The challenge (read the official material first, it's public, no login needed)
Base URL: `https://builderr.ai`. Download and read, in this order, and save copies into `docs/official/`:
- `/starter-briefs/signalpost.md` (full brief) · `/starter-briefs/signalpost-sources.md` (**permitted sources**, obey strictly)
- `/starter-briefs/signalpost-agent-playbook.md` · `/starter-briefs/signalpost-learning-harness.md`
- `/docs/signalpost-evaluation-harness.md` (evaluation contract) · starter kit `/signalpost-starter-kit.tar.gz` (Python example + a sample company)
- Company universe: `/signalpost-company-universe-2025.jsonl.gz` (411,160 companies; use it for practice batches)
If any file's details conflict with this brief, **the official files win**. Note the conflict in REPORT.md.

**Task:** given a file of **100 Norwegian organisation numbers**, research each company from permitted public sources and return
**exactly 100 terminal result envelopes** (states: `available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, `failed`),
covering company details, personnel/roles, locations, financial results, job postings and public activity. **Every fact** carries
a source URL, retrieval date and reporting period. Reruns must be **idempotent** and detect real changes (keep earlier evidence, no
duplicates or false changes, explain "what changed").

**Scoring (100):** coverage and recall 35 · accuracy 30 · refresh/change detection 20 · summary usability 10 · interface 5. **Qualify at ≥65.**
**Instant disqualifiers:** fewer than 100 results, no single reproducible command, not reading the provided input file, failing a
clean install, using personal account credentials, fabricated facts, unsafe secret handling. **A wrong-company fact blocks
qualification**: when unsure, return `ambiguous` or `not_available`. Never guess. Never put 0 where the value is unknown.

**Limits per 100-company run:** 45 minutes · ≤2,000 outbound HTTP requests (retries/redirects count, cache hits free) · $10 declared
API cost · 8 vCPU / 16 GB. **Our target cost: $0.** The official run uses **no API keys at all**: deterministic extraction
(the Brønnøysund Register Centre open APIs are the backbone: Enhetsregisteret units/sub-units/roles, the annual-accounts register,
announcements, plus the company's own website, if the sources file permits them). An optional LLM summary path may exist behind a flag, off by default.

**Deadlines:** revisions accepted until **Oct 18, 2026** (up to 5 versions); entries close Oct 21. Ashok registers on Unstop by Oct 17.
**Submission** (Claude/Ashok send it; you prepare it): ≥1,000 completed profiles, org-number manifest, repo URL + exact commit hash,
one-command run instruction, models/APIs/licences used, expected cost per 100-company run.

## Milestones (in order, commit after each, and report per PROTOCOL.md)
- **M1**: fetch and read all official docs + starter kit; write `docs/SPEC_NOTES.md` (exact output schema, permitted sources,
  evaluation contract in your own words, open questions). Scaffold the repo, run the starter kit's sample end-to-end.
- **M2**: source clients (Brønnøysund etc., per permitted list) with polite rate-limiting, retries, an on-disk cache and a request counter
  that enforces the 2,000 cap. Company resolution that can **never** attach facts to the wrong company (org-number anchored).
- **M3**: extractors for every category → envelopes with evidence (url, retrieved_at, period). All six terminal states handled.
- **M4**: refresh/change detection: snapshot store, idempotent re-runs, change log with explanations; tests proving no false changes.
- **M5**: profile summaries (what the company does, what changed, what's unknown, with sources), plus a small static web viewer
  (desktop + mobile) to find, compare and verify companies.
- **M6**: the evaluation loop: run the learning harness / local scorer on practice batches from the universe file; measure coverage,
  time, and request count per 100. Iterate on recall without risking accuracy. Record every run in `runs/`.
- **M7**: the clean-machine test: fresh clone → empty venv → the declared install step → the one run command with a 100-org input file.
  It must pass in < 45 min with < 2,000 requests. Produce ≥1,000 completed profiles for the submission.
- **M8**: `SUBMISSION.md`: everything the submission email needs (manifest, command, cost, licences, models=none), plus README.

## Hard rules
- Stay inside `~/second`. **Never** push, publish, deploy, email, sign up, or submit anything. Commit locally only.
- Obey the permitted-sources list and robots.txt. Honest User-Agent. No scraping of sites that aren't permitted.
- No fabricated or inferred financial values. Missing means missing.
