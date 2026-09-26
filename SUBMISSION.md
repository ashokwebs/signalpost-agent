# Signalpost submission email (Ashok sends from his own address to submit@builderr.ai)

**Subject:** Signalpost entry v1: <agent name> (exact-company Norwegian research agent)

Hi Builderr team,

Please find my Signalpost Round 1 entry (version 1):

- **Repository:** <public GitHub URL>
- **Exact commit hash:** <git rev-parse HEAD after publishing>
- **Completed profiles:** 1,000 (`submission/profiles-1000.jsonl.gz`, envelopes in `submission/envelopes-1000.jsonl.gz`)
- **Organisation-number manifest:** `submission/manifest-1000.txt`
- **Run command:**
  `uv sync && uv run python scripts/run_competition_batch.py --organisations <batch.jsonl> --bulk <brreg-enheter.csv.gz> --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id <id> --expected-count 100`
- **Models / APIs / licences:** no models; official Brønnøysund APIs (Enhetsregisteret, Regnskapsregisteret) and verified
  company-owned websites; open-source Python dependencies pinned in uv.lock. Built on the Builderr reference agent.
- **Expected third-party cost per 100-company batch:** $0
- **Agent name:** <name>
- **Contact for results:** <email>

Thanks!
<name>
