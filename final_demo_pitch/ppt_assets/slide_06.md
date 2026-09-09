# Slide 6 — The 3.6× bug story *(F5)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## On-slide

- We found a **unit error in our own pipeline** — a dataset column labelled km/h was actually m/s
- That error had been inflating every drift figure **3.6×**
- Same code: reported **972%** drift → **2.4%** once fixed
- Why it matters: you only find that by understanding the physics and the data

## Speaker (~20 s)

> “We owned a bug in our own pipeline: a column labelled kilometres per hour was metres per second, inflating every drift by three-point-six times. Same code went from a nonsense nine-hundred-seventy-two percent drift to two-point-four percent after the fix. That’s how you know we built it — we found the physics error ourselves.”

## Source

- `docs/AUDIT_AND_PLAN.md`
