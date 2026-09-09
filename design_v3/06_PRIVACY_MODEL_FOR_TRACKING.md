# 06 — The privacy model for live tracking

**The problem:** our strongest F8 asset is *"no user data leaves the device."*
We are now building a dashboard where phones upload live position to a server.
Handled carelessly, the new feature destroys the old claim.

**The resolution turns it into our best privacy moment.**

---

## A. Two products, two data postures — say it plainly

| | **COAST Navigator** | **COAST Command** |
|---|---|---|
| What it is | The navigation app — the PS deliverable | The fleet console — the logistics use case |
| Data posture | **Fully on-device. Nothing leaves.** | **Explicitly opt-in telemetry.** Tracking is the point. |
| Who wants it | A driver | A fleet operator who *needs* to know where their vehicle is |
| Default | Always on | **Off.** Requires scanning a QR — a deliberate physical act |

**The framing:** these are not the same product with a setting. They are two
products that share a core. The navigation engine never phones home. The fleet
layer is a separate, opt-in surface — and for a logistics operator, tracking is
not a privacy violation, it is the entire product.

**Say:** *"The navigation core never sends anything anywhere. Fleet tracking is a
different product for a different customer, it's off by default, and turning it
on requires physically scanning a code. You did that a minute ago — here is
exactly what it gave us."*

---

## B. The move that wins F8 — "What we know about you"

On the dashboard, every paired device gets a panel showing **every field we hold
about it**, in plain language, live:

```
  WHAT WE KNOW ABOUT Judge-1

  Device label        Judge-1            (you chose this)
  Session token       a3f9…c21           (expires in 6 min)
  Positions received  412
  First seen          09:38:04
  Last seen           09:41:17
  Path history        412 points, 1.2 km

  What we do NOT collect:
  ✗ Device identifier, IMEI, or advertising ID
  ✗ Phone number, email, or any account
  ✗ Contacts, photos, or any other app's data
  ✗ Anything at all when the app is closed

  [ Delete this device and all its data ]
```

**Then press the button in front of the judge.** The device and its entire track
disappear from the map instantly.

Why this scores a 10 rather than a 7: every team will *claim* privacy. We will be
the team that **shows the data we hold and deletes it on request, live, on
stage.** It takes fifteen seconds, it is unforgettable, and it is the same move
as the claim linter — converting an assertion into a demonstration.

It also happens to be exactly what data-protection regulation is built around
(access and erasure), which lands with a legally-literate judge without us
claiming a compliance certification we have not earned.

---

## C. Design rules for the pairing flow

**Consent must be legible, not buried.**

1. **The QR scan screen states what will be shared, before scanning:**
   > *"Pairing shares your live position with this dashboard until you unpair.
   > Nothing else is sent. No account, no device ID."*
2. **A persistent, unmissable indicator while paired.** A bar in the app:
   *"● Sharing position with COAST Command · Stop"*. Same visual weight as a
   recording indicator. The user must never be able to forget it is on.
3. **One-tap unpair**, always reachable from the Drive screen — not buried in
   settings.
4. **Auto-expiry.** Sessions die after ~10 minutes of inactivity and tokens are
   short-lived nonces. Data does not accumulate silently.
5. **No identifiers.** Devices are labelled by a name the *user* picks
   ("Judge-1"), never by hardware ID, IMEI, or advertising ID. **We must not be
   able to re-identify a device across sessions**, and that should be true by
   construction, not by policy.

---

## D. What must not happen

- **Do not** let the tracker flavour's behaviour bleed into the `standard` build.
  Today `LanUploader` exists only under `src/tracker/` and the standard flavour
  has no uploader at all. **Keep that separation absolutely.** It is what makes
  the two-products claim true rather than rhetorical.
- **Do not** enable tracking by default in any build.
- **Do not** collect anything not shown in the panel in §B. If a field is not
  worth showing the judge, do not collect it.
- **Do not** persist device data beyond the session without an explicit,
  separate opt-in.
- **Do not** weaken the wording of the Navigator claim to accommodate Command.
  The Navigator claim stays exactly as it is; Command is described separately.

---

## E. The updated F8 wording

Replaces the single claim in `win_tuning/F8_SECURITY_AND_PRIVACY.md` §B with a
two-part statement. Both halves are verifiable.

> **COAST Navigator — no user data leaves the device.** Position, sensor data and
> trajectories are computed and stored entirely on the phone. The app declares
> `INTERNET` for one purpose only: fetching public OpenStreetMap basemap tiles.
> With the basemap off, network traffic is zero.
>
> **COAST Command — opt-in fleet telemetry.** A separate, off-by-default surface
> for operators who need vehicle visibility. Pairing requires physically scanning
> a code. It sends position only, holds no device identifier or account, expires
> automatically, and every field held is visible and deletable on demand.

**Still never say:** "no INTERNET permission" · "zero network" without the
basemap-off qualifier · "GDPR compliant" · "encrypted" without saying what.

---

## F. The questions this must survive

> *"So data does leave the phone now."*

> "For the navigation app, no — never. What you're seeing on that dashboard is a
> separate product for fleet operators, and it's off unless you physically scan a
> pairing code. You scanned one a minute ago. Here's every single field it gave
> us —" *(open the panel)* "— no device ID, no account, no identifier of any kind.
> And this button deletes all of it." *(press it)*

> *"Could you re-identify my phone later?"*

> "No, and not as a policy — by construction. We never receive a hardware
> identifier. The device is labelled with a name you chose, tied to a session
> token that expires in minutes. Once that session is gone there is nothing to
> match against."

> *"What if the server is compromised?"*

> "It holds live position for currently-paired sessions and nothing else — no
> accounts, no identifiers, no history beyond the session. The blast radius is
> the smallest we could make it, because the most reliable way to protect data is
> not to collect it."

---

## G. Acceptance

- [ ] "What we know about you" panel implemented, showing real fields only
- [ ] Delete button works instantly and visibly
- [ ] Consent text shown *before* scanning
- [ ] Persistent sharing indicator in the app while paired
- [ ] One-tap unpair from Drive
- [ ] No hardware identifiers collected anywhere — verify in the privacy report
- [ ] `standard` flavour still contains no uploader
- [ ] Tracking off by default in every build
- [ ] F8 wording updated in the deck to the two-part statement
