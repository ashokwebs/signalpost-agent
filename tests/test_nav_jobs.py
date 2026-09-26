import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from norway_company_agent.nav_jobs import active_by_name, job_evidence, name_key


def _fetch_factory(detail_by_uuid):
    def fetch(uuid):
        return detail_by_uuid.get(uuid), "a" * 64, f"https://pam-stilling-feed.nav.no/api/v1/feedentry/{uuid}"
    return fetch


def test_publishes_only_org_number_matches():
    index = {"u1": {"s": "ACTIVE", "b": "Fjord Bygg AS"}, "u2": {"s": "ACTIVE", "b": "FJORD BYGG AS"},
             "u3": {"s": "INACTIVE", "b": "Fjord Bygg AS"}}
    by_name = active_by_name(index)
    assert set(by_name[name_key("Fjord Bygg AS")]) == {"u1", "u2"}
    details = {
        "u1": {"ad_content": {"title": "Tømrer", "employer": {"orgnr": "999888777"}, "published": "2026-09-20T10:00:00+02:00"}},
        "u2": {"ad_content": {"title": "Snekker", "employer": {"orgnr": "111222333"}}},  # same name, different entity
    }
    ev = job_evidence({"organisation_number": "999888777", "name": "FJORD BYGG AS"}, by_name, _fetch_factory(details))
    assert ev["status"] == "available"
    postings = ev["value"]["postings"]
    assert [p["title"] for p in postings] == ["Tømrer"]
    assert postings[0]["relationship"] == "advertiser"


def test_checked_zero_is_not_found():
    ev = job_evidence({"organisation_number": "123456789", "name": "Nobody AS"}, {}, _fetch_factory({}))
    assert ev["status"] == "not_found" and ev["value"]["candidates_checked"] == 0


def test_recruiter_flag():
    by_name = {name_key("Allcare Solutions AS"): ["x"]}
    details = {"x": {"ad_content": {"title": "Lærer", "employer": {"orgnr": "934213785",
               "description": "AllCare Solutions AS håndterer rekrutteringen og står derfor som annonsør."}}}}
    ev = job_evidence({"organisation_number": "934213785", "name": "ALLCARE SOLUTIONS AS"}, by_name, _fetch_factory(details))
    assert ev["value"]["postings"][0]["recruiting_on_behalf_flag"] is True
