# F5 — Technical Execution
*"Prototype, code quality, and technology stack"* · Round 1

---

## A. What this criterion actually rewards

- **Prototype** — does it exist and run, or is it slideware?
- **Code quality** — would a competent engineer respect this repo?
- **Technology stack** — are the choices deliberate and justified?

The failure mode is invisibility: we have a genuinely strong repo, and a judge in
a ninety-second window will see **none of it** unless we surface it. This
criterion is won by making depth *visible in seconds*.

## B. What we actually have (the honest inventory)

| Layer | Reality |
|---|---|
| Android app | Kotlin, 66 files, Compose/M3, builds debug + release + AAB, all flavours; JVM unit suite green |
| Lab / ML | Python, 84 files; training, benchmarking, ablations, figure generation; results committed as `summary.md` |
| Core engine | C++, shared core → Android JNI + WASM + headless edge daemon; **120,305 Hz** measured |
| Web console | React 19 + MapLibre + Vite; live phone map + real training stream |
| Data | IO-VNBD real UK drives, vehicle CAN ground truth, 43 real GNSS outages |

**The honest gap, stated up front:** the app has never run a real field drive.
Everything is validated on recorded real-world data and on-device replay. Say
this before a judge finds it.

## C. The three artifacts that win this criterion

Ordinary "we wrote good code" claims score 6. These three score 10 because they
are checkable in seconds.

### 5.1 — The claim linter (Phase 0)  ← the single best F5 artifact we have

`tools/verify_claims.py` refuses to build if any slide, screen, or document
contains a number that is not in `CLAIMS.json` with a measured source.

**The demo move, fifteen seconds:** run `python tools/verify_claims.py
--demo-failure`. It plants a fabricated number and the build fails, naming the
file and line.

No other team will have this. It converts "we're rigorous" from an adjective into
an executable. It scores F5 and F8 simultaneously, and it makes every other
number in the deck more credible by association.

### 5.2 — The bug we found in our own pipeline

We found a unit error in our own code that was inflating every drift figure by
**3.6×**. We found it, fixed it, and re-ran everything it invalidated.

Write it up properly in `docs/ENGINEERING_EVIDENCE.md`: what the bug was, how it
surfaced, what it invalidated, what we re-ran, and what process change followed.

**Why this is worth more than a feature:** anyone can show working code. Very few
teams can show that they *audited themselves and found something*. It is the
single strongest available evidence that our other numbers are trustworthy —
because it demonstrates that when our pipeline was wrong, we caught it rather
than shipping it.

### 5.3 — Code that refuses to guess

The audit found `try_map_in_loop` has three distinct refusal paths, each carrying
an explicit `"honesty"` string, and the synthetic fixture is deliberately placed
outside the OSM coverage area with the comment *"honest: map-in-loop needs
independent OSM coverage; do not invent it"* — so the harness **refuses to
score** rather than fabricate an improvement, and reports FAIL.

Similarly, the map graph's `report.json` records `built_from_drive_data: false` —
"no IO-VNBD trajectory, GNSS fix or CSV column was read while building this
graph." That is a pre-emptive answer to *"did you leak your test set into your
map?"*, which is the sharpest question a machine-learning judge can ask.

**Showing a judge code that refuses to produce a number is a stronger trust
signal than any number.** Have these three snippets bookmarked and ready.

## D. Tasks

- **5.1** `docs/ENGINEERING_EVIDENCE.md`: real per-language file/LOC counts, test
  counts and which suites pass, the measured performance table, and the one
  command that runs everything. Numbers must be generated, not typed.
- **5.2** `tools/verify_all.py` (or `make verify`) → unit suites + claim linter +
  build + privacy report, printing one clean summary table. **This is the command
  we run in front of a judge.**
- **5.3** The 3.6× bug case study, written up properly.
- **5.4** Bookmark the three "refuses to guess" code locations for Q&A.
- **5.5** Apply all of `PHASE0_BLOCKING_FIXES.md` — especially FIX-1 (the 2.02×
  row) and FIX-2 (the silent fallback). A judge who finds FIX-2 unfixed will
  reasonably conclude the whole ledger is decorative.
- **5.6** Squash the duplicate `085aac8`/`ad8a023` commits; a duplicated message in
  the log is a small, free credibility loss.
- **5.7** One architecture diagram showing the shared C++ core → three targets.

## E. Stack justification (have one line ready for each)

A judge may ask "why this and not that." Each answer is one sentence:

- **Kotlin + Compose** — the platform-native path; Compose makes the map-overlay
  HUD straightforward.
- **MapLibre + OpenStreetMap, not Google Maps** — no API key, no billing, works
  fully offline, and OSM covers places licensed maps do not. This is a
  *feasibility* and *inclusivity* decision, not a cost-saving one.
- **ONNX Runtime Mobile** — train in PyTorch, run anywhere; decouples the model
  from the app.
- **C++ core** — one implementation, three targets (phone, web, edge). Avoids the
  classic trap of the phone and the server disagreeing.
- **Particle filter, not EKF** — the state space is a graph; belief at a junction
  is genuinely multi-modal and a Gaussian cannot represent it.

## F. Language discipline

**Say:**
- "Every number we publish is linted against a measured source. Here — watch it
  fail on a fake one."
- "We found a unit bug in our own pipeline that inflated our drift numbers 3.6×.
  We fixed it and re-ran everything."
- "The harness refuses to score map-in-loop when there's no independent map
  coverage. We'd rather report FAIL than invent an improvement."

**Never say:**
- "Production-ready." It is a prototype validated on recorded data.
- "Fully tested." Say what is tested: JVM unit suite, lab benchmarks, on-device
  replay. Field drives are not done.
- Test counts or LOC figures from memory — generate them.

## G. The questions that decide this criterion

> *"How do I know you didn't just make these numbers up?"*

> "Two ways. First, every number is in `CLAIMS.json` with the file that produced
> it and the command that recomputes it — and the build fails if a number appears
> that isn't. Second, the numbers include our failures: our GNSS+INS fusion is a
> 1.07× wash, our alignment work was 32%→32%, and our speed model loses to a
> naive hold on per-window RMSE. Nobody fabricating results fabricates those."

> *"Did your map contain the answer? Is this leakage?"*

> "No, and we checked deliberately — the graph's build report records
> `built_from_drive_data: false`: no trajectory, GNSS fix, or CSV column from the
> drives was read while building the road graph. It's independent OSM data."

> *"What's the weakest part of your code?"*

> "The app has never run a real field drive — everything is validated on recorded
> real-world data and on-device replay. And our uncertainty estimate doesn't work;
> it correlates −0.23 with actual error, so we gated it off rather than show a
> user a number we don't trust."

## H. Acceptance

- [ ] `verify_all` runs everything and prints one summary table
- [ ] `verify_claims.py --demo-failure` visibly catches a planted number
- [ ] `docs/ENGINEERING_EVIDENCE.md` with generated counts, not typed
- [ ] 3.6× bug case study written up
- [ ] All Phase-0 blocking fixes applied
- [ ] Duplicate commits squashed
- [ ] Architecture diagram: one core → three targets
- [ ] Every team member can answer §G
