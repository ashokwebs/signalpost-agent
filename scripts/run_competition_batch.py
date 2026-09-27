#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.batch import profile_complete_for_modules, profiles_from_bulk, read_organisation_inputs, terminal_envelope, validate_envelopes  # noqa: E402
from norway_company_agent.evidence import utc_now  # noqa: E402
from norway_company_agent.identity import apply_website_identity_gate  # noqa: E402
from norway_company_agent.official import fetch_official_modules  # noqa: E402
from norway_company_agent.website import fetch_website  # noqa: E402
from norway_company_agent.candidates import email_domain_candidate, name_domain_candidates  # noqa: E402
from norway_company_agent.activity import activity_evidence  # noqa: E402
from norway_company_agent.nav_jobs import NavDetailFetcher, active_by_name, job_evidence, load_index  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluator-owned Signalpost batch contract")
    parser.add_argument("--organisations", required=True, help="JSON, JSONL, or text organisation-number list")
    parser.add_argument("--bulk", required=True, help="Frozen Brreg entity snapshot")
    parser.add_argument("--output", required=True, help="Terminal envelope JSONL")
    parser.add_argument("--profiles-output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-count", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retry-budget-seconds", type=float, default=600, help="time budget for the second-chance pass")
    parser.add_argument("--retry-rounds", type=int, default=2, help="passes over transient failures")
    parser.add_argument("--retry-spacing", type=float, default=1.5, help="seconds between second-chance requests")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--email-domain-candidates", action=argparse.BooleanOptionalAction, default=True,
                        help="derive a website candidate from the registry e-mail domain when no homepage is registered")
    parser.add_argument("--name-token-candidates", action=argparse.BooleanOptionalAction, default=True,
                        help="probe <legal-name-tokens>.no / .com (max 3 probes) for companies with no registry homepage and no usable e-mail domain")
    parser.add_argument("--activity", action=argparse.BooleanOptionalAction, default=True,
                        help="read dated activity from the verified website's own RSS/Atom feed or news pages")
    parser.add_argument("--nav-index", default=None,
                        help="path to the NAV job-feed index (scripts/nav_feed_index.py); enables the hiring module")
    parser.add_argument("--modules", default="registry,accounting_obligation,registry_live,financials,roles,group,locations,website")
    args = parser.parse_args()

    started_at = utc_now()
    organisation_inputs = read_organisation_inputs(args.organisations)
    orgs = [item["organisation_number"] for item in organisation_inputs]
    if len(orgs) != args.expected_count:
        raise SystemExit(f"Expected {args.expected_count} organisations, received {len(orgs)}")
    profiles, registry_metadata = profiles_from_bulk(args.bulk, orgs)
    annotations = {item["organisation_number"]: item for item in organisation_inputs}
    for profile in profiles:
        for key in ("evaluation_split", "sample_slice"):
            if key in annotations[profile["organisation_number"]]:
                profile[key] = annotations[profile["organisation_number"]][key]
    requested_modules = [item.strip() for item in args.modules.split(",") if item.strip()]
    fetch_modules = set(requested_modules) - {"registry", "accounting_obligation", "website"}
    operations = {"requests": 0, "bytes": 0, "latencies_ms": []}
    nav_by_name = active_by_name(load_index(args.nav_index)) if args.nav_index else None
    nav_fetch = NavDetailFetcher() if nav_by_name is not None else None

    def enrich(profile: dict) -> tuple[dict, dict]:
        records, metrics = fetch_official_modules(profile["organisation_number"], fetch_modules)
        profile["evidence"].update(records)
        website_metrics = {"requests": 0, "bytes": 0, "latencies_ms": []}
        if "website" in requested_modules:
            website_record, website_metrics = fetch_website(profile.get("website"))
            website_record = apply_website_identity_gate(profile, website_record)["website"]
            email_candidate_usable = False
            if not profile.get("website") and args.email_domain_candidates:
                candidate = email_domain_candidate(profile)
                if candidate:
                    cand_record, cand_metrics = fetch_website(candidate)
                    cand_record = apply_website_identity_gate(profile, cand_record)["website"]
                    for key in ("requests", "bytes"):
                        website_metrics[key] += cand_metrics[key]
                    website_metrics["latencies_ms"] += cand_metrics["latencies_ms"]
                    cand_record["discovery_method"] = "registry_email_domain"
                    cand_record["discovery_evidence"] = {"registry_email_domain": candidate}
                    website_record = cand_record
                    if (cand_record.get("value") or {}).get("identity_assessment", {}).get("publishable"):
                        email_candidate_usable = True

            if not profile.get("website") and not email_candidate_usable and getattr(args, "name_token_candidates", True):
                for candidate in name_domain_candidates(profile, limit=3):
                    cand_record, cand_metrics = fetch_website(candidate)
                    cand_record = apply_website_identity_gate(profile, cand_record)["website"]
                    for key in ("requests", "bytes"):
                        website_metrics[key] += cand_metrics[key]
                    website_metrics["latencies_ms"] += cand_metrics["latencies_ms"]
                    if (cand_record.get("value") or {}).get("identity_assessment", {}).get("publishable"):
                        cand_record["discovery_method"] = "legal_name_tokens_probe"
                        cand_record["discovery_evidence"] = {"probed_url": candidate}
                        website_record = cand_record
                        break

            profile["evidence"]["website"] = website_record
        activity_requests = 0
        if "website" in requested_modules and args.activity:
            profile["evidence"]["activity"], activity_requests = activity_evidence(profile)
        nav_requests = 0
        if nav_by_name is not None:
            before = nav_fetch.requests
            profile["evidence"]["jobs"] = job_evidence(profile, nav_by_name, nav_fetch)
            nav_requests = nav_fetch.requests - before
        metric = {
            "requests": len(metrics) + website_metrics["requests"] + nav_requests + activity_requests,
            "bytes": sum(item.bytes_received for item in metrics) + website_metrics["bytes"],
            "latencies_ms": [item.elapsed_ms for item in metrics] + website_metrics["latencies_ms"],
        }
        profile["run_metrics"] = metric
        return profile, metric

    state: dict[str, dict] = {}
    resumed_profiles = 0
    profiles_output = Path(args.profiles_output)
    if args.resume and profiles_output.exists():
        prior = [json.loads(line) for line in profiles_output.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not set(item["organisation_number"] for item in prior).issubset(set(orgs)):
            raise SystemExit("Resume profile membership is not a subset of this batch")
        state = {
            item["organisation_number"]: item
            for item in prior
            if profile_complete_for_modules(item, requested_modules)
        }
        resumed_profiles = len(state)
    pending_profiles = [profile for profile in profiles if profile["organisation_number"] not in state]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(enrich, profile): profile["organisation_number"] for profile in pending_profiles}
        for index, future in enumerate(as_completed(futures), 1):
            profile, metric = future.result()
            state[profile["organisation_number"]] = profile
            operations["requests"] += metric["requests"]
            operations["bytes"] += metric["bytes"]
            operations["latencies_ms"].extend(metric["latencies_ms"])
            if index % args.checkpoint_every == 0 or index == len(pending_profiles):
                checkpoint = [state[org] for org in orgs if org in state]
                write_jsonl(profiles_output, checkpoint)

    # Second-chance pass: official modules that failed with a transient server error (e.g. Regnskapsregisteret 503 under
    # load) are retried sequentially and slowly, inside a time budget, so rate limiting doesn't cost coverage.
    retry_deadline = time.monotonic() + args.retry_budget_seconds
    retried = recovered = 0
    for org in [o for _round in range(args.retry_rounds) for o in orgs]:
        profile = state.get(org)
        if not profile or time.monotonic() > retry_deadline:
            continue
        for module in sorted(fetch_modules):
            record = profile["evidence"].get(module) or {}
            if record.get("status") != "source_error" or not str(record.get("note") or "").startswith("HTTP 5"):
                continue
            if time.monotonic() > retry_deadline:
                break
            time.sleep(args.retry_spacing)
            records, metrics = fetch_official_modules(org, {module})
            retried += 1
            operations["requests"] += len(metrics)
            new = records.get(module) or {}
            new["retry_count"] = int(record.get("retry_count") or 0) + 1
            profile["evidence"][module] = new
            recovered += new.get("status") == "available"
    if retried:
        print(f"second-chance pass: retried {retried}, recovered {recovered}", file=sys.stderr)
        write_jsonl(profiles_output, [state[org] for org in orgs if org in state])

    completed_at = utc_now()
    ordered_profiles = [state[org] for org in orgs]
    envelopes = [
        terminal_envelope(profile, run_id=args.run_id, modules=requested_modules + (["activity"] if args.activity and "website" in requested_modules else []) + (["jobs"] if nav_by_name is not None else []), started_at=started_at, completed_at=completed_at)
        for profile in ordered_profiles
    ]
    validation = validate_envelopes(envelopes, args.expected_count)
    write_jsonl(profiles_output, ordered_profiles)
    write_jsonl(Path(args.output), envelopes)
    latencies = sorted(operations.pop("latencies_ms"))
    operations["p50_ms"] = latencies[len(latencies) // 2] if latencies else None
    operations["p95_ms"] = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else None
    report = {
        "run_id": args.run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "expected_count": args.expected_count,
        "emitted_envelopes": len(envelopes),
        "resumed_profiles": resumed_profiles,
        "profiles_fetched_this_run": len(pending_profiles),
        "modules": requested_modules,
        "registry": registry_metadata,
        "operations": operations,
        "validation": validation,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if validation["passed"] else 1)


if __name__ == "__main__":
    main()
