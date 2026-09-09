# Slide 7 — Architecture & dual deliverable *(F2)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## Conclusion headline (largest type)

**One core runs on a ₹15,000 phone and a 200 Hz edge box.**

## Dominant visual (one)

`diagrams/architecture.png` — single shared C++ core → phone + edge. Cut any second stack diagram.

## Support (≤18 pt body)

- **JNI / Android @ 10 Hz** — consumer phone app
- **Headless C++ daemon @ 200 Hz** — FOG-grade IMUs (edge engine the PS demands)
- Measured edge engine: **120,305 Hz** · **8.3 µs/sample** · **7.5 MB** *(200 Hz requirement met **600×**)*
- GNSS→DR handover **100 ms**
- Stack: Kotlin/Compose · MapLibre + OSM · ONNX Runtime Mobile · C++ core · **all offline**

## Speaker (~25 s)

> “One C++ core, two deployments: phone at ten hertz, and a headless edge daemon at two hundred hertz for FOG-grade IMUs. Measured throughput one hundred twenty thousand three hundred five hertz — six hundred times the requirement. Handover from GNSS to dead reckoning in one hundred milliseconds.”

## Sources

- Edge throughput: `core/cpp/apps/README.md`
- Handover: `lab/stress/results/`
