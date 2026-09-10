# COAST console threat model

Short and real. Scope: the demo laptop console (`web/coast_console.py`) and
phone pairing/ingest during a venue demo. Not a product security assessment.

## Who can reach the console?

Anyone on the same network as the laptop — venue LAN or the laptop's hotspot.
Assume an unfriendly device is on that network. Default bind should be loopback;
LAN exposure is an operator choice for pairing, not a free gift to the room.

## What can they do?

`/ingest` and pairing mint/claim (`/api/pair/new`, token on first POST) are
**deliberately unauthenticated** so a phone can join without an account. Blast
radius is bounded by:

- body size caps and JSON-only POSTs
- strict lat/lon, mode, speed, and token shape checks (reject, do not coerce)
- per-IP rate limits on ingest and pair mint
- capped devices and points per device (in-memory only)
- path-safe file serving for `/figures/<name>` and APK download roots

An attacker on the LAN can still spam those open endpoints within the caps, or
read live fleet positions once they know a device is paired. They cannot invent
a paired device without a valid short-lived QR token.

## What is worth stealing?

**Live positions of paired phones** for the duration of the demo session.
Nothing else by design: no accounts, no passwords, no IMEI / advertising ID /
phone number / email. Device labels are console-assigned (`Judge-N`); session
tokens are short-lived nonces. Position data lives in memory unless the
operator opts into a session log.

## What we are not defending against

- Physical access to the presenter laptop (filesystem, process list, memory)
- A compromised phone or malicious APK installed by the user
- A determined state-level adversary, targeted malware, or long-term APT
- Confidentiality of training subprocess output on the same machine
- Claims of regulatory compliance frameworks (we do not assert GDPR or similar)

## Privacy framing we protect

We hold no durable identity, so there is nothing durable to leak. Hardening
keeps that sentence true: bound open endpoints, delete for real, and never
collect identifiers we would then have to protect.
