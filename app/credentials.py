"""Signed work credentials as W3C Verifiable Credentials (VC 2.0 data model) in
compact JWS form (VC-JWT), signed with Ed25519.

The issuer key is published as a did:web document at /.well-known/did.json, so
anyone holding the credential can verify the signature without trusting our
database. A signature proves who issued the claim, not that the claim is true;
that is why each credential also carries an evidence level and a trust weight.
"""
import base64
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_PATH = Path(os.getenv("ISSUER_KEY_PATH", Path(__file__).resolve().parent.parent / "data" / "issuer_key.pem"))


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_key() -> Ed25519PrivateKey:
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEY_PATH.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return key


def issuer_did() -> str:
    host = urlparse(os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")).netloc
    return "did:web:" + host.replace(":", "%3A")


def public_jwk() -> dict:
    raw = load_key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"kty": "OKP", "crv": "Ed25519", "x": b64u(raw)}


def did_document() -> dict:
    did = issuer_did()
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did,
        "verificationMethod": [{"id": did + "#key-1", "type": "JsonWebKey2020", "controller": did,
                                "publicKeyJwk": public_jwk()}],
        "assertionMethod": [did + "#key-1"],
    }


def issue(worker: dict, job: dict, employer: dict, attestation: dict) -> tuple[str, dict]:
    """Return (vc_jwt, vc_payload) for one employer-confirmed completed job."""
    did = issuer_did()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    vc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": "urn:uuid:" + str(uuid.uuid4()),
        "type": ["VerifiableCredential", "WorkCompletionCredential"],
        "issuer": did,
        "validFrom": now,
        "credentialSubject": {
            "id": f"urn:kelasapass:worker:{worker['id']}",
            "name": worker["name"],
            "trade": job["trade"],
            "locality": job["locality"],
            "jobId": job["id"],
            "completedOn": now[:10],
            "attestedBy": {"name": employer["name"], "verificationLevel": employer["level"]},
            "finished": attestation["finished"],
            "onTime": attestation["on_time"],
            "wouldRehire": attestation["rehire"],
            "evidenceLevel": attestation["evidence_level"],
        },
    }
    header = {"alg": "EdDSA", "typ": "vc+jwt", "kid": did + "#key-1"}
    payload = dict(vc, iat=int(time.time()))
    signing_input = b64u(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        b64u(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    sig = load_key().sign(signing_input.encode())
    return signing_input + "." + b64u(sig), vc


def verify(token: str) -> dict:
    try:
        h, p, s = token.split(".")
        header = json.loads(b64u_decode(h))
        if header.get("alg") != "EdDSA":
            return {"valid": False, "reason": "unsupported alg"}
        load_key().public_key().verify(b64u_decode(s), (h + "." + p).encode())
        return {"valid": True, "payload": json.loads(b64u_decode(p))}
    except InvalidSignature:
        return {"valid": False, "reason": "signature does not match issuer key"}
    except Exception as e:  # malformed token
        return {"valid": False, "reason": f"malformed credential: {e.__class__.__name__}"}
