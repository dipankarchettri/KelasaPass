"""Trust layer: evidence levels, collusion flags, credential weights, scam guard.

Star ratings inflate and are easy to fake. Instead each credential records how
strong its evidence is, and fraud signals cut its weight:

  L0  employer verified by phone only
  L1  employer business identity checked (Udyam / GST; mocked in the MVP)
  L2  payment-linked: a UPI reference for this job
  L3  L2 plus a geotagged photo taken near the job site
"""
import re
from datetime import datetime, timedelta, timezone

from .geo import haversine_km

LEVEL_WEIGHT = {0: 0.25, 1: 0.5, 2: 0.8, 3: 1.0}
# MVP mock: format check on the 12-digit UPI reference only. Real matching of the
# payment to this job needs a payment-provider API.
UPI_REF = re.compile(r"^\d{12}$")
PHOTO_RADIUS_KM = 1.0
BURST_WINDOW = timedelta(hours=1)
BURST_LIMIT = 3
PER_EMPLOYER_CAP = 3


def evidence_level(employer: dict, job: dict, upi_ref: str | None, photo: dict | None) -> int:
    level = 1 if employer.get("business_verified") else 0
    if upi_ref and UPI_REF.match(upi_ref.strip()):
        level = 2
        if photo and haversine_km(photo["lat"], photo["lon"], job["lat"], job["lon"]) <= PHOTO_RADIUS_KM:
            level = 3
    return level


def collusion_flags(worker: dict, employer: dict, history: list[dict], now: datetime | None = None) -> list[str]:
    """history: earlier credentials (dicts with worker_id, employer_id, issued_at, employer_device)."""
    now = now or datetime.now(timezone.utc)
    flags = []
    if worker.get("device_id") and worker["device_id"] == employer.get("device_id"):
        flags.append("same_device")
    if worker.get("phone") and worker["phone"] == employer.get("phone"):
        flags.append("same_phone")
    recent = [c for c in history if c["employer_id"] == employer["id"]
              and now - datetime.fromisoformat(c["issued_at"]) <= BURST_WINDOW]
    if len(recent) >= BURST_LIMIT:
        flags.append("burst")
    pair = [c for c in history if c["employer_id"] == employer["id"] and c["worker_id"] == worker["id"]]
    if len(pair) >= PER_EMPLOYER_CAP:
        flags.append("repeat_pair_cap")
    if worker.get("employer_id_of_own") and worker["employer_id_of_own"] == employer["id"]:
        flags.append("self_attestation")
    created = employer.get("created_at")
    if created and now - datetime.fromisoformat(created) < timedelta(days=7) and not employer.get("business_verified"):
        flags.append("new_unverified_employer")
    return flags


FLAG_PENALTY = {
    "same_device": 0.05, "same_phone": 0.0, "self_attestation": 0.0, "burst": 0.3,
    "repeat_pair_cap": 0.3, "new_unverified_employer": 0.6,
}


def credential_weight(level: int, flags: list[str], rehire: bool) -> float:
    w = LEVEL_WEIGHT[level] * (1.0 if rehire else 0.7)
    for f in flags:
        w *= FLAG_PENALTY.get(f, 1.0)
    return round(w, 3)


# ---------- scam guard ----------
FEE_PATTERNS = [
    r"registration\s*fee", r"training\s*fee", r"deposit", r"advance\s*(?:payment|amount)?", r"pay\s*(?:rs|₹)",
    r"security\s*amount", r"processing\s*fee",
    r"ಶುಲ್ಕ", r"ಠೇವಣಿ", r"ಹಣ\s*ಕಳುಹಿಸಿ", r"ಮುಂಗಡ",          # fee, deposit, send money, advance
    r"फीस", r"शुल्क", r"जमा\s*राशि", r"पैसे\s*भेज", r"एडवांस",   # fee, fee, deposit, send money, advance
]
SCAM_WARNING = {
    "kn": "ಎಚ್ಚರಿಕೆ: ನಿಜವಾದ ಕೆಲಸಕ್ಕೆ ಯಾರೂ ಹಣ ಕೇಳುವುದಿಲ್ಲ. ಈ ಸಂದೇಶವನ್ನು ತಡೆಯಲಾಗಿದೆ.",
    "hi": "सावधान: असली नौकरी के लिए कोई पैसे नहीं माँगता। यह संदेश रोक दिया गया है।",
    "en": "Warning: no real job asks you for money. This message was blocked.",
}


def is_fee_request(text: str) -> bool:
    return any(re.search(p, text, re.I) for p in FEE_PATTERNS)
