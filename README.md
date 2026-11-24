# KelasaPass

**Every finished job becomes proof.**

KelasaPass is a voice-first WhatsApp assistant for blue-collar workers in Tumakuru, Karnataka. Workers create a profile by sending a voice note in Kannada or Hindi. Local employers post jobs the same way. The system matches by skill, distance, availability and verified work history. When an employer confirms a finished job, the worker gets a **signed, portable skill credential** that anyone can verify.

wHACKiest 2026, Track 4 (UnlockED): problems 4.1 (Localized Vocational Skill Verification) and 4.3 (Hyper-Local Job Matching).

## The problem

- Only 4.2% of Indians aged 15-59 have formal vocational training (PLFS 2025). Most trade skill is learned on the job and never certified.
- 31.89 crore unorganised workers are registered on e-Shram (Aug 2026), 1.07 crore of them in Karnataka (Mar 2025).
- Hiring at labour stands is a morning lottery that ends by noon. Job apps are text-first and metro-first, and job-fee scams target exactly these workers.
- Nobody gives the worker portable proof of the work they have actually done.

## What the MVP does

| Feature | Where |
|---|---|
| Voice/text note to structured profile in Kannada, Hindi or English, read back for a yes/no | `app/extract.py`, `app/service.py` |
| Employer job posts by voice/text, with worker count, wage, place and day extracted | `app/extract.py` |
| Matching on trade + distance (Haversine) + verified history + rate, with spoken-style reasons | `app/matching.py` |
| One-tap employer confirmation mints a **W3C Verifiable Credential (VC 2.0 data model) as an Ed25519-signed VC-JWT** | `app/credentials.py` |
| Issuer key published as `did:web` at `/.well-known/did.json` | `app/main.py` |
| Evidence levels instead of star ratings: L0 phone, L1 business ID, L2 UPI payment, L3 + geotagged photo | `app/trust.py` |
| Collusion flags (same device, same phone, bursts, repeat pairs, new unverified employer) that cut credential weight | `app/trust.py` |
| Scam guard: blocks employer messages asking workers for fees, warns in Kannada and Hindi | `app/trust.py` |
| WhatsApp webhook (Twilio sandbox), voice notes via ElevenLabs Scribe, voice replies via ElevenLabs TTS | `app/main.py`, `app/voice.py` |
| Optional LLM extraction via Amazon Bedrock | `app/extract.py` |
| Web demo console and public QR profile page with "Verify signature" and "Tamper test" | `web/` |

## Run it (no API keys needed)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Demo data for Tumakuru loads automatically.

**Demo script**
1. **Worker phone:** pick "Kannada electrician", send, and the bot reads the profile back in Kannada. Tap **1 (Yes)**.
2. **Employer phone:** pick "Post: 2 electricians" and send. The matches show why each worker ranked where they did. Imran ranks above a closer worker because he has payment-backed verified jobs.
3. Click **Hire**, then **Confirm job done**. Add a 12-digit UPI ref and tick the geotagged photo to get an L3 credential.
4. Open the profile, scan the QR, and click **Verify signature**, then **Tamper test** (one changed character breaks the signature).
5. Send the **Scam attempt** sample. It is blocked, and the worker-side warning appears in Kannada and Hindi.
6. **Trust panel:** stage a collusion attack. Five fake confirmations from the worker's own phone add a total weight of about 0.02, against 1.0 for one honest L3 job.

Run the tests:

```bash
python -m pytest -q
```

## Turn on voice, WhatsApp and AWS

Copy `.env.example` to `.env` and export the variables you need (see the comments there):

- **ElevenLabs:** `ELEVENLABS_API_KEY`, plus STT and TTS model IDs from the ElevenLabs docs (Kannada TTS needs an Eleven v3/v4 model) and a voice ID.
- **AWS Bedrock:** `BEDROCK_MODEL_ID` and AWS credentials. Without it, a rule-based multilingual extractor is used.
- **WhatsApp:** point the Twilio WhatsApp sandbox webhook to `https://<your-host>/webhook/twilio` and set `PUBLIC_BASE_URL`.

## Architecture

```
Worker / Employer (WhatsApp voice note)
        |
WhatsApp Cloud API / Twilio sandbox  ->  /webhook/twilio
        |
ElevenLabs Scribe (STT)  ->  Bedrock or rule-based extraction  ->  read back for yes/no
        |
Matching (trade + Haversine + verified history + rate)  ->  job alert
        |
Employer confirms  ->  trust layer (evidence level, collusion flags, weight)
        |
Ed25519 VC-JWT signed (did:web issuer)  ->  public QR profile  ->  anyone verifies
```

Planned AWS deployment: API Gateway + Lambda, DynamoDB (replacing SQLite), S3 for media and profile pages, Bedrock (extraction, Titan embeddings, Nova video pre-screen), Secrets Manager for the signing key, region ap-south-1.

## Honest limits of this MVP

- **Mocked:** the Udyam/GST business check (a flag on the employer), UPI payment matching (12-digit format check only) and photo geotags (coordinates passed in).
- **Approximate:** locality coordinates are demo values around Tumakuru.
- **Indicative:** NCO-2015 codes in `app/trades.py` need checking against the official list.
- **Signatures prove the issuer, not the truth:** a signature shows who issued a credential, not that the claim is true. Evidence levels and fraud flags carry that part.
- **Not built yet:** the optional 30-second AI video pre-screen. It will only ever be labelled as a pre-screen and never issue a credential.
