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
