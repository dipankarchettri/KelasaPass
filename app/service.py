"""Core flows shared by the WhatsApp webhook and the web demo console."""
import uuid
from datetime import datetime, timezone

from . import credentials, matching, trust
from .extract import extract
from .geo import LOCALITIES, coords
from .store import Store
from .trades import trade_label


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def readback_worker(p: dict) -> str:
    loc = p["locality"]
    years = p.get("years") or "?"
    rate = p.get("daily_rate") or "?"
    if p["lang"] == "kn":
        return (f"ನೀವು {trade_label(p['trade'], 'kn')}, {years} ವರ್ಷ ಅನುಭವ, "
                f"{LOCALITIES.get(loc, {}).get('kn', loc)}, ದಿನಕ್ಕೆ ₹{rate}. ಸರಿಯೇ? ಹೌದು ಎಂದರೆ 1 ಕಳುಹಿಸಿ.")
    if p["lang"] == "hi":
        return (f"आप {trade_label(p['trade'], 'hi')} हैं, {years} साल का अनुभव, {loc}, ₹{rate} प्रति दिन। "
                f"सही है? हाँ के लिए 1 भेजें।")
    return f"You are a {trade_label(p['trade'])}, {years} years experience, {loc}, Rs {rate}/day. Correct? Send 1 for yes."


def readback_job(j: dict) -> str:
    return (f"Job: {j['workers_needed']} x {trade_label(j['trade'])}, {j['locality']}, {j['when']}, "
            f"Rs {j.get('wage') or '?'}/day. Send 1 to post.")


class Service:
    def __init__(self, store: Store | None = None):
        self.store = store or Store()

    # ---------- workers ----------
    def worker_from_text(self, name: str, phone: str, text: str, device_id: str | None = None) -> dict:
        f = extract(text, "worker")
        if not f.get("trade"):
            return {"ok": False, "reply": "Sorry, which work do you do? (electrician, plumber, mason, painter...)"}
        lat, lon = coords(f["locality"])
        w = {"id": _id("w"), "name": name, "phone": phone, "device_id": device_id, "transcript": text,
             "trade": f["trade"], "locality": f["locality"], "lat": lat, "lon": lon, "lang": f["lang"],
             "years": f.get("years"), "daily_rate": f.get("daily_rate"), "available": True,
             "confirmed": False, "created_at": _now()}
        self.store.put("workers", w)
        self.store.log({"t": _now(), "type": "worker_draft", "worker": w["id"], "text": text})
        return {"ok": True, "worker": w, "reply": readback_worker(w)}

    def confirm_worker(self, worker_id: str) -> dict:
        w = self.store.get("workers", worker_id)
        w["confirmed"] = True
        self.store.put("workers", w)
        return w

    # ---------- employers & jobs ----------
    def employer(self, name: str, phone: str, device_id: str | None = None, business_verified=False,
                 created_at: str | None = None) -> dict:
        e = {"id": _id("e"), "name": name, "phone": phone, "device_id": device_id,
             "business_verified": business_verified, "level": "L1" if business_verified else "L0",
             "created_at": created_at or _now()}
        return self.store.put("employers", e)

    def job_from_text(self, employer_id: str, text: str) -> dict:
        if trust.is_fee_request(text):
            self.store.log({"t": _now(), "type": "scam_blocked", "employer": employer_id, "text": text})
            return {"ok": False, "blocked": True, "reply": trust.SCAM_WARNING["kn"],
                    "warnings": trust.SCAM_WARNING}
        f = extract(text, "job")
        if not f.get("trade"):
            return {"ok": False, "reply": "Which worker do you need? (electrician, plumber, mason, painter...)"}
        lat, lon = coords(f["locality"])
        j = {"id": _id("j"), "employer_id": employer_id, "transcript": text, "trade": f["trade"],
             "locality": f["locality"], "lat": lat, "lon": lon, "wage": f.get("wage"),
             "workers_needed": f.get("workers_needed", 1), "when": f.get("when", "today"),
             "status": "open", "assigned": [], "created_at": _now()}
        self.store.put("jobs", j)
        self.store.log({"t": _now(), "type": "job_posted", "job": j["id"], "text": text})
        return {"ok": True, "job": j, "reply": readback_job(j)}

    def weights(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for c in self.store.all("credentials"):
            if not c.get("revoked"):
                out.setdefault(c["worker_id"], []).append(c["weight"])
        return out

    def matches(self, job_id: str) -> list[dict]:
        job = self.store.get("jobs", job_id)
        return matching.rank(job, self.store.all("workers"), self.weights())

    def accept(self, job_id: str, worker_id: str) -> dict:
        job = self.store.get("jobs", job_id)
        if worker_id not in job["assigned"]:
            job["assigned"].append(worker_id)
        self.store.put("jobs", job)
        self.store.log({"t": _now(), "type": "job_accepted", "job": job_id, "worker": worker_id})
        return job

    # ---------- completion -> credential ----------
    def confirm_completion(self, job_id: str, worker_id: str, finished=True, on_time=True, rehire=True,
                           upi_ref: str | None = None, photo: dict | None = None, device_id: str | None = None) -> dict:
        job = self.store.get("jobs", job_id)
        worker = self.store.get("workers", worker_id)
        employer = self.store.get("employers", job["employer_id"])
        if device_id:
            employer = dict(employer, device_id=device_id)  # device used for this confirmation
        if not finished:
            return {"ok": False, "reply": "Noted: job not finished. No credential issued."}
        level = trust.evidence_level(employer, job, upi_ref, photo)
        flags = trust.collusion_flags(worker, employer, self.store.all("credentials"))
        weight = trust.credential_weight(level, flags, rehire)
        att = {"finished": finished, "on_time": on_time, "rehire": rehire, "evidence_level": f"L{level}"}
        jwt, vc = credentials.issue(worker, job, employer, att)
        cred = {"id": vc["id"], "worker_id": worker_id, "employer_id": employer["id"], "job_id": job_id,
                "trade": job["trade"], "issued_at": _now(), "evidence_level": level, "flags": flags,
                "weight": weight, "jwt": jwt, "employer_name": employer["name"], "employer_level": employer["level"],
                "employer_device": employer.get("device_id"), "revoked": False}
        self.store.put("credentials", cred)
        self.store.log({"t": _now(), "type": "credential_issued", "worker": worker_id, "level": level,
                        "flags": flags, "weight": weight})
        return {"ok": True, "credential": cred}

    def profile(self, worker_id: str) -> dict | None:
        w = self.store.get("workers", worker_id)
        if not w:
            return None
        creds = sorted(self.store.credentials_for(worker_id), key=lambda c: c["issued_at"], reverse=True)
        live = [c["weight"] for c in creds if not c.get("revoked")]
        return {"worker": w, "credentials": creds, "proof_score": round(matching.proof_score(live), 3),
                "verified_jobs": sum(1 for c in creds if c["weight"] >= 0.2 and not c.get("revoked"))}
