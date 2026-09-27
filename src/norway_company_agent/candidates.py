"""Website candidates when the registry lists no homepage.

The registry's own contact e-mail (Enhetsregisteret `epostadresse`) often sits on the company's domain. That domain is
only a *candidate*: it is fetched and must pass the same exact-identity gate (organisation number or full legal name on
the homepage) before anything is published. Free-mail and ISP domains are never candidates.
"""
from __future__ import annotations

import re
from typing import Any

FREE_MAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.no", "hotmail.co.uk", "outlook.com", "outlook.no", "live.no",
    "live.com", "msn.com", "yahoo.com", "yahoo.no", "icloud.com", "me.com", "mac.com", "aol.com", "mail.com", "gmx.com",
    "gmx.net", "protonmail.com", "proton.me", "online.no", "frisurf.no", "broadpark.no", "c2i.net", "getmail.no",
    "start.no", "lyse.net", "altibox.no", "epost.no", "tele2.no", "chello.no", "bluezone.no", "haugnett.no",
    "enivest.net", "sfjbb.net", "nextgentel.com", "ebnett.no", "loqal.no", "tussa.com", "icloud.no", "yandex.com",
    "vikenfiber.no", "kvinnherad.net", "neasonline.no", "hadeland.net", "barlindhaug.no", "tdcnet.no", "online.net",
}
EMAIL = re.compile(r"^[^@\s]+@([a-z0-9.-]+\.[a-z]{2,})$", re.I)


def registry_email(profile: dict[str, Any]) -> str | None:
    value = ((profile.get("evidence") or {}).get("registry") or {}).get("value") or {}
    email = (value.get("epostadresse") or "").strip()
    return email or None


def email_domain_candidate(profile: dict[str, Any]) -> str | None:
    """Return 'https://<domain>/' for a non-free-mail registry e-mail domain, else None."""
    email = registry_email(profile)
    if not email:
        return None
    match = EMAIL.match(email)
    if not match:
        return None
    domain = match.group(1).lower().strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if domain in FREE_MAIL or domain.endswith((".kommune.no", ".gov.no")):
        return None
    return f"https://{domain}/"


STOPWORDS = {"i", "og", "and", "pa", "for", "av", "til"}
LEGAL_TAIL = {
    "as", "asa", "ans", "da", "enk", "iks", "sa", "sam", "sti", "stiftelsen",
    "nuf", "ab", "ltd", "limited", "inc",
}
GENERIC_TAIL = {
    "holding", "invest", "eiendom", "norge", "gruppen", "consulting",
    "drift", "service", "bygg", "forvaltning", "kapital",
}


def name_domain_candidates(profile: dict[str, Any] | str, limit: int = 3) -> list[str]:
    """Generate up to `limit` (default 3) candidate URLs (<legal-name-tokens>.no / .com) for a company name.

    Probes are ordered by likelihood:
    1. Joined tokens on .no (https://<tokens>.no/)
    2. Base name without generic suffix (e.g. holding/norge) on .no, or hyphenated tokens on .no
    3. Joined tokens on .com (https://<tokens>.com/)
    """
    import unicodedata

    name = profile.get("name") if isinstance(profile, dict) else str(profile)
    text = str(name or "").translate(str.maketrans({"ø": "o", "Ø": "O", "å": "a", "Å": "A", "æ": "ae", "Æ": "AE"}))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = [w for w in re.findall(r"[a-z0-9]+", text)]
    while words and words[-1] in LEGAL_TAIL:
        words.pop()
    if not words:
        return []

    content_words = [w for w in words if w not in STOPWORDS] or words
    joined = "".join(content_words)
    hyphen = "-".join(content_words)
    cands: list[str] = []

    if len(content_words) == 1:
        if len(content_words[0]) >= 3:
            cands.append(f"https://{content_words[0]}.no/")
            cands.append(f"https://{content_words[0]}.com/")
    else:
        cands.append(f"https://{joined}.no/")
        if content_words[-1] in GENERIC_TAIL and len(content_words) >= 2:
            base_joined = "".join(content_words[:-1])
            if len(base_joined) >= 3:
                cands.append(f"https://{base_joined}.no/")
            cands.append(f"https://{joined}.com/")
        else:
            cands.append(f"https://{hyphen}.no/")
            cands.append(f"https://{joined}.com/")

    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= limit:
            break
    return out

