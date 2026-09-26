from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .evidence import evidence, utc_now
from .official import accounting_obligation_assessment
from .sampling import iter_bulk


TERMINAL_STATES = {
    "complete",
    "not_applicable",
    "not_found",
    "blocked_policy",
    "blocked_robots",
    "source_error",
    "budget_exhausted",
    "submission_error",
}


def read_organisation_inputs(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    values: list[Any]
    if source.suffix == ".json":
        body = json.loads(text)
        values = body if isinstance(body, list) else body.get("organisation_numbers", [])
    elif source.suffix == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        values = [line.strip() for line in text.splitlines() if line.strip()]
    records = []
    for value in values:
        org = value.get("organisation_number") if isinstance(value, dict) else value
        org = "".join(character for character in str(org or "") if character.isdigit())
        if len(org) != 9:
            raise ValueError(f"Invalid Norwegian organisation number: {value!r}")
        record = {"organisation_number": org}
        if isinstance(value, dict):
            for key in ("evaluation_split", "sample_slice"):
                if value.get(key) is not None:
                    record[key] = value[key]
        records.append(record)
    orgs = [record["organisation_number"] for record in records]
    if len(orgs) != len(set(orgs)):
        raise ValueError("Organisation-number input contains duplicates")
    return records


def read_organisation_numbers(path: str | Path) -> list[str]:
    return [record["organisation_number"] for record in read_organisation_inputs(path)]


def profiles_from_bulk(path: str | Path, organisation_numbers: Iterable[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested = list(organisation_numbers)
    wanted = set(requested)
    snapshot_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    retrieved_at = utc_now()
    found: dict[str, dict[str, Any]] = {}
    scanned = 0
    for profile in iter_bulk(path):
        scanned += 1
        org = profile["organisation_number"]
        if org not in wanted:
            continue
        raw = profile.pop("raw", {})
        profile["evidence"] = {
            "registry": evidence(
                "registry",
                "available",
                "official_registry_bulk",
                "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                value=raw,
                retrieved_at=retrieved_at,
                content_sha256=snapshot_sha256,
                source_row_key=org,
            ),
            "accounting_obligation": accounting_obligation_assessment(profile),
        }
        found[org] = profile
        if len(found) == len(wanted):
            break
    missing = [org for org in requested if org not in found]
    live_fallback = []
    for org in missing:
        # Never crash or drop an input: entities absent from the bulk snapshot are anchored on the live entity API,
        # and if that fails too they still get a profile whose registry evidence says so (terminal state, not a gap).
        found[org] = profile_from_live_registry(org, retrieved_at)
        live_fallback.append(org)
    return [found[org] for org in requested], {
        "bulk_missing_live_fallback": live_fallback,
        "registry_snapshot_sha256": snapshot_sha256,
        "registry_rows_scanned": scanned,
        "requested": len(requested),
        "selected": len(found),
    }


def evidence_terminal_state(record: dict[str, Any] | None) -> str:
    if not record:
        return "submission_error"
    status = record.get("status")
    if status == "available":
        return "complete"
    if status == "not_applicable":
        return "not_applicable"
    if status == "not_found":
        return "not_found"
    if status == "blocked":
        note = str(record.get("note") or "").casefold()
        return "blocked_robots" if "robot" in note else "blocked_policy"
    if status == "source_error":
        return "source_error"
    return "submission_error"


def terminal_envelope(
    profile: dict[str, Any],
    *,
    run_id: str,
    modules: Iterable[str],
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    module_states = {}
    for module in modules:
        record = profile.get("evidence", {}).get(module)
        module_states[module] = {
            "state": evidence_terminal_state(record),
            "retry_count": int((record or {}).get("retry_count") or 0),
            "final_timestamp": (record or {}).get("retrieved_at") or completed_at,
        }
    entity_state = "submission_error" if any(item["state"] == "submission_error" for item in module_states.values()) else "complete"
    return {
        "run_id": run_id,
        "organisation_number": profile["organisation_number"],
        "state": entity_state,
        "started_at": started_at,
        "completed_at": completed_at,
        "modules": module_states,
        "profile": profile,
    }


def validate_envelopes(envelopes: list[dict[str, Any]], expected_count: int) -> dict[str, Any]:
    orgs = [item.get("organisation_number") for item in envelopes]
    invalid_states = [
        {"organisation_number": item.get("organisation_number"), "state": state.get("state")}
        for item in envelopes
        for state in item.get("modules", {}).values()
        if state.get("state") not in TERMINAL_STATES
    ]
    checks = {
        "exact_expected_count": len(envelopes) == expected_count,
        "unique_organisation_numbers": len(orgs) == len(set(orgs)),
        "all_entity_states_terminal": all(item.get("state") in TERMINAL_STATES for item in envelopes),
        "all_module_states_terminal": not invalid_states,
        "zero_silent_drops": len(envelopes) == expected_count and len(orgs) == len(set(orgs)),
    }
    return {"passed": all(checks.values()), "checks": checks, "invalid_states": invalid_states}


def profile_complete_for_modules(profile: dict[str, Any], modules: Iterable[str]) -> bool:
    records = profile.get("evidence", {})
    return all(module in records and records[module].get("status") != "not_fetched" for module in modules)


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "_links":
                continue
            flat.update(_flatten(child, f"{prefix}{key}."))
    elif isinstance(value, list):
        flat[prefix[:-1]] = ", ".join(str(v) for v in value if not isinstance(v, (dict, list)))
    else:
        flat[prefix[:-1]] = "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    return flat


def profile_from_live_registry(org: str, retrieved_at: str) -> dict[str, Any]:
    """Build the same profile shape as the bulk CSV row from the live Enhetsregisteret entity endpoint."""
    from .http import fetch_json
    url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}"
    result = fetch_json(url)
    base: dict[str, Any] = {"organisation_number": org, "name": None, "legal_form": None, "employees": None,
                            "bankrupt": None, "liquidating": None, "municipality": None, "municipality_number": None,
                            "industry_code": None, "industry_label": None, "website": "", "latest_submitted_accounts": None}
    if result.status != 200 or not isinstance(result.body, dict):
        status = "not_found" if result.status in (404, 410) else "source_error"
        base["evidence"] = {"registry": evidence("registry", status, "official_registry_live", url, value=None,
                                                 retrieved_at=result.retrieved_at or retrieved_at,
                                                 content_sha256=result.content_sha256, note=result.error)}
        base["evidence"]["accounting_obligation"] = accounting_obligation_assessment(base)
        return base
    raw = _flatten(result.body)
    raw["organisasjonsnummer"] = org
    employees = raw.get("antallAnsatte")
    base.update({
        "name": raw.get("navn"), "legal_form": raw.get("organisasjonsform.kode"),
        "employees": int(employees) if employees and employees.isdigit() else None,
        "bankrupt": raw.get("konkurs") == "true", "liquidating": raw.get("underAvvikling") == "true",
        "municipality": raw.get("forretningsadresse.kommune"), "municipality_number": raw.get("forretningsadresse.kommunenummer"),
        "industry_code": raw.get("naeringskode1.kode"), "industry_label": raw.get("naeringskode1.beskrivelse"),
        "website": raw.get("hjemmeside") or "", "latest_submitted_accounts": raw.get("sisteInnsendteAarsregnskap"),
    })
    base["evidence"] = {"registry": evidence("registry", "available", "official_registry_live", url, value=raw,
                                             retrieved_at=result.retrieved_at, content_sha256=result.content_sha256,
                                             source_row_key=org)}
    base["evidence"]["accounting_obligation"] = accounting_obligation_assessment(base)
    return base
