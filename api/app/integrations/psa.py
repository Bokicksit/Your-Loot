"""PSA — the slab, by its certification number.

A graded card's identity is on its own label: year, set, subject, variety,
card number, grade. The cert number is the key to all of it, so a slab needs
no catalogue lookup at all — which is what makes this work for cards our
Pokémon dump has never heard of, and for sports cards it never will.

Free token from https://www.psacard.com/publicapi — set PSA_API_KEY. Bearer
auth, one endpoint, and a daily call budget that third parties put around 100;
PSA don't state it, so treat a 429 as the real answer.

Images only exist for cards graded from October 2021 onward. Older slabs come
back with everything except a picture, which is a normal answer here, not a
failure — photograph the slab instead.
"""

import httpx

from app.config import settings

API = "https://api.psacard.com/publicapi"


class PsaError(Exception):
    """Carries an HTTP status the router can translate for its own callers."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _year(value) -> int | None:
    text = str(value or "").strip()[:4]
    return int(text) if text.isdigit() else None


class PsaClient:
    def __init__(self):
        self.api_key = settings.psa_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def by_cert(self, cert: str) -> dict | None:
        """The card behind a cert number, or None if PSA doesn't know it."""
        digits = "".join(c for c in str(cert) if c.isdigit())
        if not digits:
            raise PsaError(400, "a PSA cert number is digits only")
        try:
            r = httpx.get(
                f"{API}/cert/GetByCertNumber/{digits}",
                headers={"Authorization": f"bearer {self.api_key}"},
                timeout=20,
            )
        except httpx.HTTPError as e:
            raise PsaError(502, f"PSA unreachable: {e}")
        if r.status_code == 401:
            raise PsaError(502, "PSA rejected the API key")
        if r.status_code == 429:
            raise PsaError(429, "PSA lookups exhausted for today")
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise PsaError(502, f"PSA error: {r.status_code}")

        cert_data = (r.json() or {}).get("PSACert") or {}
        if not cert_data.get("CertNumber"):
            return None
        return self._summarise(cert_data)

    def _summarise(self, c: dict) -> dict:
        subject = (c.get("Subject") or "").strip()
        number = (c.get("CardNumber") or "").strip()
        # The label reads "2025 POKEMON DRI EN"; Brand carries that whole
        # string, which is the closest thing to a set name PSA gives us.
        brand = (c.get("Brand") or "").strip()
        grade = (c.get("CardGrade") or "").strip()
        return {
            "cert_number": str(c.get("CertNumber")).strip(),
            "title": subject or brand or "Graded card",
            "subject": subject or None,
            "set_name": brand or None,
            "card_number": number or None,
            "rarity": (c.get("Variety") or "").strip() or None,
            "year": _year(c.get("YearIssued")),
            # PSA writes the grade as a word plus a number ("MINT 9"); the
            # number alone is what a grade field holds.
            "grade": _grade_number(grade),
            "grade_label": grade or None,
            "category": (c.get("Category") or "").strip() or None,
            "image_url": (c.get("ImageURL") or "").strip() or None,
            "population": c.get("TotalPopulation"),
            "population_higher": c.get("PopulationHigher"),
        }


def _grade_number(text: str) -> str | None:
    """"MINT 9" -> "9", "GEM MT 10" -> "10", "AUTHENTIC" -> None."""
    for part in reversed(str(text or "").split()):
        cleaned = part.replace(".", "", 1)
        if cleaned.isdigit():
            return part
    return None


psa_client = PsaClient()
