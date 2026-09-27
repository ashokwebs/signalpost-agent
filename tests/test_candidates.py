import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from norway_company_agent.candidates import (  # noqa: E402
    email_domain_candidate,
    name_domain_candidates,
)


def test_email_domain_candidate():
    prof = {"evidence": {"registry": {"value": {"epostadresse": "contact@mycompany.no"}}}}
    assert email_domain_candidate(prof) == "https://mycompany.no/"

    freemail = {"evidence": {"registry": {"value": {"epostadresse": "owner@gmail.com"}}}}
    assert email_domain_candidate(freemail) is None


def test_name_domain_candidates_single_token():
    cands = name_domain_candidates("ASPERIA AS")
    assert cands == ["https://asperia.no/", "https://asperia.com/"]


def test_name_domain_candidates_two_tokens_generic_tail():
    cands = name_domain_candidates("WYSSEN NORGE AS")
    assert "https://wyssennorge.no/" in cands
    assert "https://wyssen.no/" in cands
    assert len(cands) <= 3


def test_name_domain_candidates_hyphenated_and_com():
    cands = name_domain_candidates("BOAR COLLECT AS")
    assert cands == [
        "https://boarcollect.no/",
        "https://boar-collect.no/",
        "https://boarcollect.com/",
    ]


def test_name_domain_candidates_norwegian_characters():
    cands = name_domain_candidates("HØILAND GARD AS")
    assert cands[0] == "https://hoilandgard.no/"
    assert "https://hoiland-gard.no/" in cands


def test_name_domain_candidates_stopwords_handled():
    cands = name_domain_candidates("MUSIKK I INNLANDET AS")
    assert "https://musikkinnlandet.no/" in cands


def test_candidate_gating_behavior():
    from norway_company_agent.identity import apply_website_identity_gate

    profile = {"organisation_number": "936056210", "name": "ASPERIA AS"}
    # Website matching legal name tokens on homepage
    matching_web = {
        "status": "available",
        "source_url": "https://asperia.no/",
        "value": {
            "final_url": "https://asperia.no/",
            "title": "Asperia AS - Konsulenttjenester",
            "main_text_excerpt": "Velkommen til Asperia AS. Vi leverer rådgivning og konsulenttjenester til bedrifter i hele Norge med fokus på kvalitet og langsiktig vekst.",
            "pages": [],
            "social_links": [],
        },
    }
    gated = apply_website_identity_gate(profile, matching_web)
    assert gated["assessment"]["publishable"] is True

    # Website not matching identity (e.g. parked page)
    unmatched_web = {
        "status": "available",
        "source_url": "https://other.no/",
        "value": {
            "final_url": "https://other.no/",
            "title": "Domain for sale",
            "main_text_excerpt": "This domain is for sale.",
            "pages": [],
            "social_links": [],
        },
    }
    gated_bad = apply_website_identity_gate(profile, unmatched_web)
    assert gated_bad["assessment"]["publishable"] is False

