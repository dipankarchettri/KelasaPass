"""Rank workers for a job: same trade, nearby, available, affordable, and with
stronger verified work history. Every match carries plain reasons so the bot can
say "why you matched" out loud."""
import math

from .geo import haversine_km

RADIUS_KM = 10.0
W_DISTANCE, W_PROOF, W_RATE = 0.45, 0.35, 0.20


def proof_score(credential_weights: list[float]) -> float:
    """Diminishing returns on total credential weight, in [0, 1)."""
    return 1 - math.exp(-sum(credential_weights) / 3.0)


def rank(job: dict, workers: list[dict], weights_by_worker: dict[str, list[float]], radius_km=RADIUS_KM) -> list[dict]:
    results = []
    for w in workers:
        if w.get("trade") != job.get("trade") or not w.get("available", True) or not w.get("confirmed"):
            continue
        d = haversine_km(w["lat"], w["lon"], job["lat"], job["lon"])
        if d > radius_km:
            continue
        proof = proof_score(weights_by_worker.get(w["id"], []))
        rate, wage = w.get("daily_rate"), job.get("wage")
        rate_fit = 1.0 if not rate or not wage or rate <= wage else max(0.0, 1 - (rate - wage) / wage)
        score = W_DISTANCE * (1 - d / radius_km) + W_PROOF * proof + W_RATE * rate_fit
        n_creds = len(weights_by_worker.get(w["id"], []))
        reasons = [f"{d:.1f} km away"]
        reasons.append(f"{n_creds} verified job{'s' if n_creds != 1 else ''}" if n_creds else "no verified jobs yet")
        if rate and wage:
            reasons.append(f"asks Rs {rate}/day vs offer Rs {wage}")
        results.append({"worker": w, "distance_km": round(d, 2), "proof": round(proof, 3),
                        "score": round(score, 3), "reasons": reasons})
    return sorted(results, key=lambda r: r["score"], reverse=True)
