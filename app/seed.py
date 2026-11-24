"""Demo data for Tumakuru: workers, employers and some earlier verified jobs."""
from datetime import datetime, timedelta, timezone

from .service import Service

OLD = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(timespec="seconds")

WORKERS = [
    ("Ramesh", "+91-90000-00001", "ನಾನು ಎಲೆಕ್ಟ್ರಿಷಿಯನ್, 8 ವರ್ಷ ಅನುಭವ, ಎಸ್ ಎಸ್ ಪುರಂ, ದಿನಕ್ಕೆ 800 ರೂಪಾಯಿ"),
    ("Imran", "+91-90000-00002", "मैं इलेक्ट्रीशियन हूँ, 5 साल, गुब्बी गेट gubbi gate, 750 रुपये"),
    ("Suresh", "+91-90000-00003", "Electrician, 2 years, Kyathasandra, Rs 700"),
    ("Lakshmi", "+91-90000-00004", "ನಾನು ಪೇಂಟರ್, 6 ವರ್ಷ, ಬಟವಾಡಿ, ದಿನಕ್ಕೆ 700 ರೂಪಾಯಿ"),
    ("Manjunath", "+91-90000-00005", "ಗಾರೆ ಕೆಲಸ ಮೇಸ್ತ್ರಿ, 12 ವರ್ಷ, ಕ್ಯಾತಸಂದ್ರ, ದಿನಕ್ಕೆ 1000 ರೂಪಾಯಿ"),
    ("Ravi", "+91-90000-00006", "Plumber 4 years Shettihalli Rs 750"),
]


def seed(svc: Service) -> dict:
    svc.store.reset()
    ids = {}
    for name, phone, text in WORKERS:
        w = svc.worker_from_text(name, phone, text, device_id=f"dev-{name.lower()}")["worker"]
        svc.confirm_worker(w["id"])
        ids[name] = w["id"]
    hw = svc.employer("Sri Lakshmi Hardware", "+91-80000-00001", "dev-hw", business_verified=True, created_at=OLD)
    gc = svc.employer("Ganesh Constructions", "+91-80000-00002", "dev-gc", business_verified=True, created_at=OLD)
    home = svc.employer("Anitha (household)", "+91-80000-00003", "dev-anitha", created_at=OLD)
    ids.update(hardware=hw["id"], constructions=gc["id"], household=home["id"])

    # earlier jobs that Imran and Manjunath completed, confirmed with payment evidence
    for emp, worker, text, upi in [
        (hw, "Imran", "Need 1 electrician at Gubbi Gate, Rs 800", "412398765012"),
        (gc, "Imran", "1 electrician wiring at SS Puram, Rs 850", "412398765013"),
        (home, "Imran", "electrician for fan wiring at Batawadi Rs 700", None),
        (gc, "Manjunath", "2 mason at Kyathasandra Rs 1000", "412398765014"),
    ]:
        job = svc.job_from_text(emp["id"], text)["job"]
        svc.accept(job["id"], ids[worker])
        svc.confirm_completion(job["id"], ids[worker], upi_ref=upi,
                               photo={"lat": job["lat"], "lon": job["lon"]} if upi else None)
    return ids
