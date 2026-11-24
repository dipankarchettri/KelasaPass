import os
import tempfile

TMP = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(TMP, "test.db")
os.environ["ISSUER_KEY_PATH"] = os.path.join(TMP, "key.pem")

from fastapi.testclient import TestClient

from app import credentials, trust
from app.extract import extract
from app.main import app

client = TestClient(app)


def test_extract_kannada_worker():
    f = extract("ನಾನು ಎಲೆಕ್ಟ್ರಿಷಿಯನ್, 8 ವರ್ಷ ಅನುಭವ, ಎಸ್ ಎಸ್ ಪುರಂ, ದಿನಕ್ಕೆ 800 ರೂಪಾಯಿ", "worker")
    assert f == {"trade": "electrician", "locality": "ss puram", "lang": "kn", "years": 8, "daily_rate": 800}


def test_extract_hindi_job_count_and_wage():
    f = extract("मुझे कल batawadi में 2 इलेक्ट्रीशियन चाहिए, 900 रुपये", "job")
    assert (f["trade"], f["workers_needed"], f["wage"], f["when"], f["lang"]) == ("electrician", 2, 900, "tomorrow", "hi")


def test_scam_guard_blocks_fee_requests():
    assert trust.is_fee_request("Pay Rs 500 registration fee first")
    assert trust.is_fee_request("ಕೆಲಸಕ್ಕೆ ಮೊದಲು ಶುಲ್ಕ ಕಟ್ಟಿ")
    assert not trust.is_fee_request("Need 2 masons at Kyathasandra, Rs 1000")


def test_matching_prefers_verified_history():
    ids = client.post("/api/seed").json()
    job = client.post("/api/jobs", json={"employer_id": ids["hardware"],
                                         "text": "Need 2 electricians at SS Puram tomorrow Rs 900"}).json()["job"]
    names = [m["worker"]["name"] for m in client.get(f"/api/jobs/{job['id']}/matches").json()]
    # Imran is 2 km further than Ramesh but has payment-backed verified jobs
    assert names[0] == "Imran" and set(names) == {"Imran", "Ramesh", "Suresh"}


def test_completion_issues_verifiable_credential_and_tamper_fails():
    ids = client.post("/api/seed").json()
    job = client.post("/api/jobs", json={"employer_id": ids["hardware"], "text": "1 electrician at SS Puram Rs 900"}).json()["job"]
    client.post(f"/api/jobs/{job['id']}/accept", json={"worker_id": ids["Ramesh"]})
    cred = client.post(f"/api/jobs/{job['id']}/complete", json={
        "worker_id": ids["Ramesh"], "upi_ref": "412398765099", "photo_lat": job["lat"], "photo_lon": job["lon"]}).json()["credential"]
    assert cred["evidence_level"] == 3 and cred["flags"] == [] and cred["weight"] == 1.0
    ok = client.post("/api/verify", json={"jwt": cred["jwt"]}).json()
    assert ok["valid"] and ok["payload"]["credentialSubject"]["trade"] == "electrician"
    h, p, s = cred["jwt"].split(".")
    bad = h + "." + p[:-2] + ("A" if p[-2] != "A" else "B") + p[-1] + "." + s
    assert not credentials.verify(bad)["valid"]


def test_collusion_attack_is_worth_almost_nothing():
    ids = client.post("/api/seed").json()
    creds = client.post(f"/api/demo/collusion/{ids['Ramesh']}").json()["credentials"]
    assert all("same_device" in c["flags"] for c in creds)
    assert sum(c["weight"] for c in creds) < 0.1
    assert client.get(f"/api/workers/{ids['Ramesh']}/profile").json()["verified_jobs"] == 0


def test_whatsapp_webhook_readback_and_confirm():
    r = client.post("/webhook/twilio", data={"From": "whatsapp:+919", "Body": "Plumber 4 years Shettihalli Rs 750"})
    assert "plumber" in r.text and "Send 1" in r.text
    r = client.post("/webhook/twilio", data={"From": "whatsapp:+919", "Body": "1"})
    assert "/p/w_" in r.text


def test_did_document_exposes_ed25519_key():
    doc = client.get("/.well-known/did.json").json()
    assert doc["verificationMethod"][0]["publicKeyJwk"]["crv"] == "Ed25519"


def test_twilio_signature_enforced_when_token_set(monkeypatch):
    import base64
    import hashlib
    import hmac

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://kelasapass.example")
    form = {"From": "whatsapp:+910000000009", "Body": "hello"}
    assert client.post("/webhook/twilio", data=form).status_code == 403
    data = "https://kelasapass.example/webhook/twilio" + "".join(k + form[k] for k in sorted(form))
    sig = base64.b64encode(hmac.new(b"test-token", data.encode(), hashlib.sha1).digest()).decode()
    assert client.post("/webhook/twilio", data=form, headers={"X-Twilio-Signature": sig}).status_code == 200
