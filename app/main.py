"""KelasaPass API: web demo console, WhatsApp (Twilio) webhook, did:web issuer."""
import os
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from . import credentials, voice
from .seed import seed
from .service import Service

WEB = Path(__file__).resolve().parent.parent / "web"
MEDIA = Path(__file__).resolve().parent.parent / "data" / "media"

app = FastAPI(title="KelasaPass", description="Every finished job becomes proof.")
svc = Service()


# ---------- pages ----------
@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/p/{worker_id}")
def profile_page(worker_id: str):
    return FileResponse(WEB / "profile.html")


@app.get("/.well-known/did.json")
def did_json():
    return credentials.did_document()


# ---------- API ----------
class WorkerIn(BaseModel):
    name: str
    phone: str
    text: str
    device_id: str | None = None


class EmployerIn(BaseModel):
    name: str
    phone: str
    device_id: str | None = None
    business_verified: bool = False


class JobIn(BaseModel):
    employer_id: str
    text: str


class AcceptIn(BaseModel):
    worker_id: str


class CompleteIn(BaseModel):
    worker_id: str
    finished: bool = True
    on_time: bool = True
    rehire: bool = True
    upi_ref: str | None = None
    photo_lat: float | None = None
    photo_lon: float | None = None
    device_id: str | None = None


class VerifyIn(BaseModel):
    jwt: str


def _need(doc, what):
    if not doc:
        raise HTTPException(404, f"{what} not found")
    return doc


@app.post("/api/seed")
def api_seed():
    return seed(svc)


@app.post("/api/workers")
def api_worker(body: WorkerIn):
    return svc.worker_from_text(body.name, body.phone, body.text, body.device_id)


@app.post("/api/workers/{worker_id}/confirm")
def api_confirm_worker(worker_id: str):
    _need(svc.store.get("workers", worker_id), "worker")
    return svc.confirm_worker(worker_id)


@app.get("/api/workers")
def api_workers():
    return svc.store.all("workers")


@app.get("/api/workers/{worker_id}/profile")
def api_profile(worker_id: str):
    return _need(svc.profile(worker_id), "worker")


@app.post("/api/employers")
def api_employer(body: EmployerIn):
    return svc.employer(body.name, body.phone, body.device_id, body.business_verified)


@app.get("/api/employers")
def api_employers():
    return svc.store.all("employers")


@app.post("/api/jobs")
def api_job(body: JobIn):
    _need(svc.store.get("employers", body.employer_id), "employer")
    return svc.job_from_text(body.employer_id, body.text)


@app.get("/api/jobs/{job_id}/matches")
def api_matches(job_id: str):
    _need(svc.store.get("jobs", job_id), "job")
    return svc.matches(job_id)


@app.post("/api/jobs/{job_id}/accept")
def api_accept(job_id: str, body: AcceptIn):
    _need(svc.store.get("jobs", job_id), "job")
    return svc.accept(job_id, body.worker_id)


@app.post("/api/jobs/{job_id}/complete")
def api_complete(job_id: str, body: CompleteIn):
    _need(svc.store.get("jobs", job_id), "job")
    photo = {"lat": body.photo_lat, "lon": body.photo_lon} if body.photo_lat is not None else None
    return svc.confirm_completion(job_id, body.worker_id, body.finished, body.on_time, body.rehire,
                                  body.upi_ref, photo, body.device_id)


@app.post("/api/verify")
def api_verify(body: VerifyIn):
    res = credentials.verify(body.jwt)
    if res.get("valid"):
        cred = svc.store.get("credentials", res["payload"]["id"])
        res["revoked"] = bool(cred and cred.get("revoked"))
        res["weight"] = cred["weight"] if cred else None
        res["flags"] = cred["flags"] if cred else None
    return res


@app.post("/api/demo/collusion/{worker_id}")
def api_collusion(worker_id: str):
    """Stage an attack: a brand-new, unverified 'employer' on the worker's own phone
    confirms five jobs within minutes. Flags fire and the credentials carry almost no weight."""
    worker = _need(svc.store.get("workers", worker_id), "worker")
    fake = svc.employer("New Contractor 9xxxx", "+91-70000-99999", device_id=worker["device_id"])
    out = []
    for _ in range(5):
        job = svc.job_from_text(fake["id"], f"1 {worker['trade']} at {worker['locality']} Rs 900")["job"]
        svc.accept(job["id"], worker_id)
        out.append(svc.confirm_completion(job["id"], worker_id)["credential"])
    return {"fake_employer": fake, "credentials": out}


@app.get("/api/events")
def api_events():
    return svc.store.events()


@app.get("/api/status")
def api_status():
    return {"voice_stt": voice.enabled(), "voice_tts": voice.tts_enabled(),
            "bedrock": bool(os.getenv("BEDROCK_MODEL_ID")), "issuer": credentials.issuer_did()}


@app.post("/api/voice")
async def api_voice(role: str = Form(...), name: str = Form("Worker"), phone: str = Form("+91-0"),
                    employer_id: str = Form(None), audio: UploadFile = File(...)):
    if not voice.enabled():
        raise HTTPException(400, "Voice is off: set ELEVENLABS_API_KEY and ELEVENLABS_STT_MODEL (see .env.example)")
    text = voice.transcribe(await audio.read(), audio.filename or "note.webm", audio.content_type or "audio/webm")
    if role == "employer":
        return dict(svc.job_from_text(employer_id, text), transcript=text)
    return dict(svc.worker_from_text(name, phone, text), transcript=text)


@app.get("/media/{name}")
def media(name: str):
    path = MEDIA / Path(name).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/mpeg")


# ---------- WhatsApp via Twilio sandbox ----------
SESSIONS: dict[str, dict] = {}  # phone -> {"pending_worker": id} (in-memory for the MVP)


def _twiml(text: str, audio_url: str | None = None) -> Response:
    media = f"<Media>{escape(audio_url)}</Media>" if audio_url else ""
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message><Body>{escape(text)}</Body>{media}</Message></Response>'
    return Response(body, media_type="application/xml")


def _voice_reply(text: str) -> str | None:
    base = os.getenv("PUBLIC_BASE_URL")
    if not (voice.tts_enabled() and base):
        return None
    MEDIA.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + ".mp3"
    (MEDIA / name).write_bytes(voice.speak(text))
    return f"{base}/media/{name}"


@app.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    form = await request.form()
    phone = form.get("From", "")
    text = (form.get("Body") or "").strip()
    if int(form.get("NumMedia", 0) or 0) > 0 and voice.enabled():
        url, ctype = form.get("MediaUrl0"), form.get("MediaContentType0", "audio/ogg")
        audio = requests.get(url, auth=(os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")),
                             timeout=30).content
        text = voice.transcribe(audio, "note.ogg", ctype)

    session = SESSIONS.setdefault(phone, {})
    if text == "1" and session.get("pending_worker"):
        w = svc.confirm_worker(session.pop("pending_worker"))
        base = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
        reply = f"ಪ್ರೊಫೈಲ್ ಸಿದ್ಧವಾಗಿದೆ. Your profile: {base}/p/{w['id']}"
        return _twiml(reply, _voice_reply("ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಸಿದ್ಧವಾಗಿದೆ."))
    if not text:
        return _twiml("Send a voice note about your work. ನಿಮ್ಮ ಕೆಲಸದ ಬಗ್ಗೆ ಧ್ವನಿ ಸಂದೇಶ ಕಳುಹಿಸಿ.")
    res = svc.worker_from_text(form.get("ProfileName", "Worker"), phone, text)
    if res.get("ok"):
        session["pending_worker"] = res["worker"]["id"]
    return _twiml(res["reply"], _voice_reply(res["reply"]))
