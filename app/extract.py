"""Turn a transcribed voice note into structured profile / job fields.

Uses Amazon Bedrock when BEDROCK_MODEL_ID is set, otherwise a deterministic
rule-based extractor so the demo runs offline. Both return the same schema, and
the bot always reads the result back for a yes/no, because speech recognition
on noisy dialect voice notes is never 100% right.
"""
import json
import logging
import os
import re

from .geo import detect_locality
from .trades import TRADES, detect_trade

KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
HI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

YEAR_WORDS = r"(?:years?|yrs?|ವರ್ಷ\S*|साल|वर्ष)"
MONEY_WORDS = r"(?:rs\.?|₹|rupees?|ರೂ\S*|रुपये|रुपए|रु\.?)"


def _norm(text: str) -> str:
    return text.translate(KN_DIGITS).translate(HI_DIGITS)


def detect_lang(text: str) -> str:
    if re.search(r"[ಀ-೿]", text):
        return "kn"
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    return "en"


def _years(t: str):
    m = re.search(r"(\d{1,2})\s*" + YEAR_WORDS, t, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _money(t: str):
    m = re.search(MONEY_WORDS + r"\s*(\d{3,5})", t, re.IGNORECASE) or re.search(r"(\d{3,5})\s*" + MONEY_WORDS, t, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _count(t: str):
    """First small number (1-20) that is not a year count or an amount, e.g. "2 electricians"."""
    for m in re.finditer(r"(?<!\d)(\d{1,2})(?!\d)", t):
        if re.match(r"\s*" + YEAR_WORDS, t[m.end():], re.IGNORECASE):
            continue
        if 1 <= int(m.group(1)) <= 20:
            return int(m.group(1))
    return 1


def rule_extract(text: str, kind: str) -> dict:
    t = _norm(text)
    out = {
        "trade": detect_trade(t),
        "locality": detect_locality(t) or "tumakuru",
        "lang": detect_lang(text),
    }
    if kind == "worker":
        out["years"] = _years(t)
        out["daily_rate"] = _money(t)
    else:
        out["wage"] = _money(t)
        out["workers_needed"] = _count(t)
        out["when"] = "tomorrow" if re.search(r"tomorrow|ನಾಳೆ|कल", t, re.IGNORECASE) else "today"
    return out


PROMPT = """Extract fields from this voice-note transcript from {who} in Tumakuru, Karnataka.
Return ONLY JSON with keys: {keys}. trade must be one of: {trades}. Use null when unknown.
Transcript: {text}"""


def bedrock_extract(text: str, kind: str):
    model = os.getenv("BEDROCK_MODEL_ID")
    if not model:
        return None
    import boto3

    keys = "trade, locality, years, daily_rate" if kind == "worker" else "trade, locality, wage, workers_needed, when"
    who = "a worker describing themselves" if kind == "worker" else "an employer posting a job"
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    resp = client.converse(
        modelId=model,
        messages=[{"role": "user", "content": [{"text": PROMPT.format(
            who=who, keys=keys, trades=", ".join(TRADES), text=text)}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )
    raw = resp["output"]["message"]["content"][0]["text"]
    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    data["lang"] = detect_lang(text)
    return data


def extract(text: str, kind: str) -> dict:
    try:
        data = bedrock_extract(text, kind)
    except Exception as e:  # noqa: BLE001 - any Bedrock/boto/JSON failure falls back to the rule extractor
        logging.getLogger(__name__).warning("Bedrock extraction failed, using rules: %s", e)
        data = None
    base = rule_extract(text, kind)
    if data:
        base.update({k: v for k, v in data.items() if v is not None})
    return base
