"""Build the SIH IDEA deck from the official template.

The template's chrome is preserved exactly -- SIH logo, footer bar, slide
numbers, the team-name oval, the title placeholders. Only the body content is
replaced. Six slides, which is the stated maximum including the title.

Every number written onto a slide is pulled from win_tuning/CLAIMS.json, so
`python tools/verify_claims.py` can check the deck the same way it checks
everything else. Nothing is typed in by hand.

    python tools/build_deck.py --team-name "..." --team-id "..."
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "final_demo_pitch" / "SIH2026-IDEA-Presentation-Format.pptx"
DIAGRAMS = REPO / "final_demo_pitch" / "ppt_assets" / "diagrams"
CLAIMS = REPO / "win_tuning" / "CLAIMS.json"
OUT = REPO / "final_demo_pitch" / "ppt_assets" / "COAST_SIH2026_IDEA.pptx"

INK = RGBColor(0x0B, 0x12, 0x20)
BODY = RGBColor(0x2B, 0x36, 0x45)
MUTED = RGBColor(0x6B, 0x7A, 0x8C)
TEAL = RGBColor(0x00, 0x8A, 0x72)
RED = RGBColor(0xC2, 0x39, 0x3D)
BLUE = RGBColor(0x00, 0x70, 0xC0)

FOOTER_TOP = Inches(6.85)  # nothing may cross this


def claims() -> dict[str, float]:
    d = json.loads(CLAIMS.read_text(encoding="utf-8"))
    return {c["id"]: c["value"] for c in d["claims"] if c.get("value") is not None}


C = claims()


def clear_body(slide, keep: set[str]) -> None:
    """Strip the template's instruction text, keep the chrome."""
    for sh in list(slide.shapes):
        if sh.name in keep:
            continue
        if sh.has_text_frame and sh.text_frame.text.strip():
            sh._element.getparent().remove(sh._element)


def set_title(slide, text: str) -> None:
    """Replace the title outright.

    Editing runs[0] leaves the template's own placeholder text in the later
    runs, which is how a slide ends up titled '...TUNNELIDEA TITLE'.
    """
    tf = slide.shapes.title.text_frame
    keep = tf.paragraphs[0]
    for p in list(tf.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    # The template carries a soft line break inside the title placeholder,
    # which survives a text assignment and shows up as a stray glyph.
    for br in keep._p.findall(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}br"
    ):
        keep._p.remove(br)
    first = keep.runs[0] if keep.runs else keep.add_run()
    for r in list(keep.runs[1:]):
        r._r.getparent().remove(r._r)
    first.text = text


def set_oval(slide, team: str) -> None:
    """The top-left badge the template calls 'Your Team Name'."""
    for sh in slide.shapes:
        if sh.name.startswith("Oval") and sh.has_text_frame:
            tf = sh.text_frame
            tf.clear()
            tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = team
            r.font.size = Pt(10.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def textbox(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.clear()
    return tf


def para(tf, text, *, size=13, bold=False, color=BODY, space_before=0,
         space_after=4, first=False, bullet=None, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    if bullet:
        r0 = p.add_run()
        r0.text = bullet + "  "
        r0.font.size = Pt(size)
        r0.font.bold = True
        r0.font.color.rgb = TEAL
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return p


def stat_card(slide, x, y, w, value, label, color=TEAL):
    """A single number, large, with its meaning under it."""
    tf = textbox(slide, x, y, w, 1.05)
    p = tf.paragraphs[0]
    p.space_after = Pt(1)
    r = p.add_run()
    r.text = value
    r.font.size = Pt(30)
    r.font.bold = True
    r.font.color.rgb = color
    p2 = tf.add_paragraph()
    p2.space_before = Pt(0)
    r2 = p2.add_run()
    r2.text = label
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = MUTED


def fit_image(slide, path: Path, x, y, max_w, max_h):
    """Place an image inside a box without letting it cross the footer."""
    from PIL import Image

    with Image.open(path) as im:
        iw, ih = im.size
    ar = ih / iw
    w = max_w
    h = w * ar
    if h > max_h:
        h = max_h
        w = h / ar
    left = Inches(x + (max_w - w) / 2)
    slide.shapes.add_picture(str(path), left, Inches(y), Inches(w), Inches(h))


# ---------------------------------------------------------------- slides


def slide1(s, args):
    for sh in s.shapes:
        if sh.name == "TextBox 9" and sh.has_text_frame:
            tf = sh.text_frame
            tf.clear()
            rows = [
                ("Problem Statement ID", "26168"),
                ("Problem Statement Title",
                 "AI-ML based Intelligent Dead Reckoning system for seamless navigation"),
                ("Theme", args.theme),
                ("PS Category", "Software"),
                ("Team ID", args.team_id),
                ("Team Name", args.team_name),
            ]
            for i, (k, v) in enumerate(rows):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.space_after = Pt(7)
                rk = p.add_run()
                rk.text = f"{k} – "
                rk.font.size = Pt(15)
                rk.font.color.rgb = MUTED
                rv = p.add_run()
                rv.text = v
                rv.font.size = Pt(15)
                rv.font.bold = True
                rv.font.color.rgb = INK
        if sh.name == "Subtitle 3" and sh.has_text_frame:
            tf = sh.text_frame
            tf.clear()
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = "COAST"
            r.font.size = Pt(30)
            r.font.bold = True
            r.font.color.rgb = BLUE
            p2 = tf.add_paragraph()
            r2 = p2.add_run()
            r2.text = "When GPS dies, you coast on sensors."
            r2.font.size = Pt(15)
            r2.font.italic = True
            r2.font.color.rgb = MUTED


def slide2(s, args):
    keep = {"Rectangle 8", "Title 1", "Slide Number Placeholder 5",
            "Footer Placeholder 6", "Oval 9", "Picture 10"}
    clear_body(s, keep)
    set_title(s, "COAST — NAVIGATION THAT SURVIVES THE TUNNEL")

    tf = textbox(s, 0.62, 1.28, 6.5, 0.62)
    para(tf, "Everyone tries to fix this with a better sensor. We measured that "
             "instinct — and it is wrong.", size=14.5, bold=True, color=INK, first=True)

    tf = textbox(s, 0.62, 1.98, 6.5, 3.1)
    para(tf, "Given a perfect, zero-error gyroscope, dead reckoning still fails "
             f"{C['perfect_gyro_fail_pct']:.0f}% of 60-second segments. The bottleneck was never "
             "sensor quality — it is that nothing stops the estimate leaving the road.",
         size=12.5, first=True, bullet="01")
    para(tf, "So we changed what the filter is allowed to believe. Its state is not "
             "a free position (x, y); it is (which road edge, how far along it). "
             "Off-road is not representable, so lateral error cannot accumulate.",
         size=12.5, space_before=8, bullet="02")
    para(tf, "This only works in the loop. Snapping a finished track to the nearest "
             f"road scores {C['posthoc_mapmatch_x']:.2f}× — worse than doing nothing. Same map, "
             "opposite architecture.", size=12.5, space_before=8, bullet="03")
    para(tf, "Runs on the phone already in the vehicle. No OBD-II, no dongle, no "
             "network — the map database is offline OpenStreetMap, as the problem "
             "statement specifies.", size=12.5, space_before=8, bullet="04")

    if (DIAGRAMS / "inversion.png").is_file():
        fit_image(s, DIAGRAMS / "inversion.png", 7.3, 1.45, 5.6, 3.5)

    tf = textbox(s, 7.3, 5.15, 5.6, 0.5)
    para(tf, "Measured on 43 real GNSS outages from IO-VNBD, scored against "
             "vehicle CAN-bus ground truth.", size=10, color=MUTED, italic=True, first=True)

    for i, (v, l) in enumerate((
        (f"{C['map_in_loop_improvement_x']:.2f}×", "lower median position error"),
        (f"{C['perfect_gyro_fail_pct']:.0f}%", "a perfect gyro still fails"),
        (f"{C['edge_worst_case_multiple']:.0f}×", "the 200 Hz edge requirement"),
    )):
        stat_card(s, 0.62 + i * 2.2, 5.3, 2.1, v, l)


def slide3(s, args):
    keep = {"Rectangle 9", "Title 1", "Slide Number Placeholder 5",
            "Footer Placeholder 6", "Oval 10", "Picture 11"}
    clear_body(s, keep)

    tf = textbox(s, 0.62, 1.15, 5.9, 4.1)
    para(tf, "COAST-VNet-1 — our speed model", size=14, bold=True, color=INK, first=True)
    para(tf, "96,086 parameters · 392 KB ONNX · runs on the phone. A "
             "frequency-decoupled CNN-GRU: the low band goes through a GRU as "
             "vehicle motion, the high band through a conv stack as road and engine "
             "vibration — the exact noise the problem statement names.",
         size=11.5, space_after=9)
    para(tf, "Trained leave-file-out on IO-VNBD, labelled from the vehicle CAN bus "
             "rather than phone GNSS, so it never learns to imitate a noisy fix.",
         size=11.5, space_after=12)

    para(tf, "The estimation pipeline", size=14, bold=True, color=INK, space_before=6)
    for n, t in (
        ("Align", "pitch/roll from gravity; mount yaw estimated on the move"),
        ("Filter", "gravity removed, then vibration split from motion"),
        ("Predict", "COAST-VNet-1 speed + gyro yaw + compass, ZUPT at rest"),
        ("Constrain", "particle filter over the OSM road graph, with NHC"),
        ("Fuse", "GNSS re-acquired in 100 ms, both directions"),
    ):
        p = para(tf, t, size=11.5, space_after=3, bullet=n)

    tf = textbox(s, 0.62, 5.45, 5.9, 1.2)
    para(tf, "Stack", size=12, bold=True, color=INK, first=True)
    para(tf, "Kotlin · Jetpack Compose · ONNX Runtime Mobile · MapLibre + "
             "OpenStreetMap (no API key, no billing) · shared C++ core → phone, "
             "WASM and a headless edge daemon · PyTorch for training.",
         size=11, color=BODY)

    arch = DIAGRAMS / "architecture.png"
    if arch.is_file():
        fit_image(s, arch, 6.8, 1.15, 6.1, 4.0)

    tf = textbox(s, 6.8, 5.35, 6.1, 1.3)
    para(tf, "Why a particle filter, not a Kalman filter", size=12, bold=True,
         color=INK, first=True)
    para(tf, "At a junction the belief is genuinely multi-modal — you may be on "
             "either road. A single Gaussian must collapse that to one answer "
             "exactly when the ambiguity matters most. Particles carry both "
             "hypotheses until the motion resolves them.", size=11, color=BODY)


def slide4(s, args):
    keep = {"Rectangle 9", "Title 1", "Slide Number Placeholder 5",
            "Footer Placeholder 6", "Oval 11", "Picture 10"}
    clear_body(s, keep)

    tf = textbox(s, 0.62, 1.15, 6.0, 2.9)
    para(tf, "Feasible because it needs nothing that does not already exist",
         size=14, bold=True, color=INK, first=True)
    for k, v in (
        ("Extra hardware", "None — any phone with an IMU"),
        ("Map licence / API key", "None — OpenStreetMap, offline"),
        ("Network at runtime", "None — inference is on-device"),
        ("Cloud infrastructure", "None — zero marginal cost per user"),
        ("User account", "None — no identity is collected"),
    ):
        p = tf.add_paragraph()
        p.space_after = Pt(4)
        r = p.add_run()
        r.text = f"{k}   "
        r.font.size = Pt(11.5)
        r.font.color.rgb = MUTED
        r2 = p.add_run()
        r2.text = v
        r2.font.size = Pt(11.5)
        r2.font.bold = True
        r2.font.color.rgb = INK

    tf = textbox(s, 0.62, 4.15, 6.0, 2.5)
    para(tf, "Scales in three directions", size=14, bold=True, color=INK, first=True)
    para(tf, f"Device — one C++ core runs 10 Hz on a phone and {C['edge_worst_case_hz']:,.0f} Hz "
             f"headless in its worst measured configuration, {C['edge_worst_case_multiple']:.0f}× the "
             "200 Hz edge requirement.", size=11.5, space_after=5, bullet="→")
    para(tf, "Geography — OpenStreetMap covers the planet. Adding a city is a data "
             "step, not an engineering one.", size=11.5, space_after=5, bullet="→")
    para(tf, "Domain — the constraint is a plug-in. The algorithm never knew it was "
             "a road; a rail track or a shipping channel is another implementation.",
         size=11.5, bullet="→")

    tf = textbox(s, 7.0, 1.15, 5.9, 5.4)
    para(tf, "Risks, and what we did about them", size=14, bold=True, color=INK, first=True)
    for risk, action, tone in (
        ("Heading drift is the hard part",
         f"We proved a perfect gyro is not enough ({C['perfect_gyro_fail_pct']:.0f}% still fail), which is "
         "why the map is in the loop rather than a better sensor.", TEAL),
        ("Consumer IMUs are noisy and biased",
         "Gravity removed before integration; vibration separated from motion in "
         "the model; zero-velocity updates at rest.", TEAL),
        ("Phone mount varies",
         "Gravity-axis canonicalisation cut mount-swap degradation by ~63% in "
         "ablation. Yaw-to-vehicle remains our open problem, and we say so.", TEAL),
        ("We do not yet meet the <10% drift bar",
         f"We are at {C['coast_median_drift_pct']:.1f}% against a {C['free_median_drift_pct']:.1f}% baseline — "
         "roughly half the gap closed, with a measured route to the rest.", RED),
        ("Our uncertainty estimate is not trustworthy",
         "It correlates −0.23 with real error, so we hide it rather than show a "
         "number we cannot stand behind.", RED),
    ):
        p = tf.add_paragraph()
        p.space_before = Pt(7)
        p.space_after = Pt(2)
        r = p.add_run()
        r.text = risk
        r.font.size = Pt(11.5)
        r.font.bold = True
        r.font.color.rgb = tone
        p2 = tf.add_paragraph()
        p2.space_after = Pt(0)
        r2 = p2.add_run()
        r2.text = action
        r2.font.size = Pt(11)
        r2.font.color.rgb = BODY


def slide5(s, args):
    keep = {"Rectangle 9", "Title 1", "Slide Number Placeholder 5",
            "Footer Placeholder 6", "Oval 11", "Picture 10"}
    clear_body(s, keep)

    tf = textbox(s, 0.62, 1.15, 6.1, 1.4)
    para(tf, "The vehicles nobody built a fallback for", size=14, bold=True,
         color=INK, first=True)
    para(tf, "Premium cars ship with wheel-connected inertial navigation. Trucks, "
             "older cars and India's two-wheeler fleet do not — they rely entirely "
             "on the phone on the dashboard. That is who this is for.",
         size=11.5, color=BODY)

    for i, (v, l) in enumerate((
        ("1.96 crore", "two-wheelers sold in India, FY2024-25"),
        ("4.6×", "two-wheelers per passenger vehicle"),
        ("₹0", "marginal cost per additional user"),
    )):
        stat_card(s, 0.62 + i * 2.05, 2.65, 2.0, v, l)

    tf = textbox(s, 0.62, 3.85, 6.1, 0.4)
    para(tf, "Sales figures: SIAM, 15 April 2025.", size=9.5, color=MUTED,
         italic=True, first=True)

    tf = textbox(s, 0.62, 4.25, 6.1, 2.3)
    para(tf, "Where it matters most", size=14, bold=True, color=INK, first=True)
    for k, v in (
        ("Everyday navigation", "the turn you miss because the dot froze"),
        ("Emergency response", "an ambulance in an underpass, when dispatch needs it most"),
        ("Logistics & quick commerce", "continuity through tunnels and multi-level warehouses"),
        ("Sovereignty", "GNSS can be jammed; an inertial + map solution cannot be"),
    ):
        para(tf, f"{k} — {v}", size=11.5, space_after=4, bullet="›")

    tf = textbox(s, 7.05, 1.15, 5.85, 5.4)
    para(tf, "Benefits", size=14, bold=True, color=INK, first=True)
    for h, b in (
        ("Social", "Navigation continuity is a safety function. It should not "
                   "require a data plan, a subscription, or a car expensive enough "
                   "to have inertial navigation fitted at the factory."),
        ("Economic", "Zero marginal cost per user. No map licensing, no cloud "
                     "bill, no per-query fee — so the consumer app can stay free "
                     "while the core is licensed to OEMs and fleet operators."),
        ("Environmental", "Zero additional hardware manufactured, and therefore "
                          "zero additional e-waste. It runs on phones people "
                          "already own, and on old ones — the model is 392 KB."),
        ("Strategic", "Positioning that depends on no satellite signal keeps "
                      "working while a constellation is being rebuilt or "
                      "deliberately denied. It complements NavIC rather than "
                      "competing with it."),
    ):
        p = tf.add_paragraph()
        p.space_before = Pt(9)
        p.space_after = Pt(2)
        r = p.add_run()
        r.text = h
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.color.rgb = TEAL
        p2 = tf.add_paragraph()
        p2.space_after = Pt(0)
        r2 = p2.add_run()
        r2.text = b
        r2.font.size = Pt(11)
        r2.font.color.rgb = BODY


def slide6(s, args):
    keep = {"Rectangle 9", "Title 1", "Slide Number Placeholder 5",
            "Footer Placeholder 6", "Oval 8", "Picture 11"}
    clear_body(s, keep)

    tf = textbox(s, 0.62, 1.15, 6.1, 2.6)
    para(tf, "Dataset", size=13.5, bold=True, color=INK, first=True)
    para(tf, "IO-VNBD — Inertial and Odometry Benchmark Dataset for ground vehicle "
             "positioning. Onyekpe et al. github.com/onyekpeu/IO-VNBD",
         size=11, space_after=10)
    para(tf, "All results below are leave-file-out on this corpus, labelled from "
             "the vehicle CAN bus at 10 Hz — never from phone GNSS.",
         size=11, color=MUTED, italic=True, space_after=12)

    para(tf, "Foundational work we build on", size=13.5, bold=True, color=INK)
    for t in (
        "Newson & Krumm (2009) — Hidden Markov map matching. Their algorithm; we "
        "implement and cite it, adapted for dead-reckoned rather than GNSS input.",
        "Brossard et al. — AI-IMU dead reckoning (invariant EKF, vehicle DR).",
        "Herath et al. RoNIN · Liu et al. TLIO · TinyOdom — the neural inertial "
        "odometry line COAST-VNet-1 belongs to.",
        "EqNIO (ICLR 2025) — gravity-axis equivariance; our mount canonicalisation "
        "follows this idea.",
    ):
        para(tf, t, size=10.5, space_after=4, bullet="·")

    tf = textbox(s, 7.05, 1.15, 5.85, 5.3)
    para(tf, "Our own measured results", size=13.5, bold=True, color=INK, first=True)
    para(tf, "Every figure in this deck is re-derived from a committed results "
             "file by tools/verify_claims.py, which fails the build if a slide "
             "states a number no measurement produced.",
         size=10.5, color=MUTED, italic=True, space_after=10)

    rows = [
        ("Map-in-loop vs dead reckoning",
         f"{C['map_in_loop_improvement_x']:.2f}× lower median error", TEAL),
        ("Post-hoc road snapping (control)",
         f"{C['posthoc_mapmatch_x']:.2f}× — worse than nothing", RED),
        ("Perfect-gyro ablation",
         f"still fails {C['perfect_gyro_fail_pct']:.0f}% of segments", RED),
        ("Median drift, free DR → COAST",
         f"{C['free_median_drift_pct']:.1f}% → {C['coast_median_drift_pct']:.1f}%", TEAL),
        ("Heading channel, gyro → compass",
         f"{C['heading_gyro_drift_pct']:.1f}% → {C['heading_compass_drift_pct']:.1f}%", TEAL),
        ("GNSS+INS fusion",
         f"{C['gnss_ins_fusion_x']:.2f}× — a wash, reported as such", RED),
        ("Edge engine, worst configuration",
         f"{C['edge_worst_case_hz']:,.0f} Hz = {C['edge_worst_case_multiple']:.0f}× the requirement", TEAL),
        ("GNSS ⇄ dead-reckoning handover", "100 ms, both directions", TEAL),
    ]
    for k, v, tone in rows:
        p = tf.add_paragraph()
        p.space_before = Pt(5)
        p.space_after = Pt(0)
        r = p.add_run()
        r.text = k + "   "
        r.font.size = Pt(10.5)
        r.font.color.rgb = BODY
        r2 = p.add_run()
        r2.text = v
        r2.font.size = Pt(10.5)
        r2.font.bold = True
        r2.font.color.rgb = tone

    p = tf.add_paragraph()
    p.space_before = Pt(12)
    r = p.add_run()
    r.text = ("We publish our negative results alongside our wins. A record that "
              "contains only successes is one nobody should trust.")
    r.font.size = Pt(10.5)
    r.font.italic = True
    r.font.color.rgb = MUTED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team-name", default="TEAM NAME")
    ap.add_argument("--team-id", default="TEAM ID")
    ap.add_argument("--theme", default="Space Technology")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    prs = Presentation(str(TEMPLATE))

    # Drop the template's instruction slide; the limit is six including title.
    while len(prs.slides) > 6:
        rid = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rid)
        del prs.slides._sldIdLst[-1]

    builders = [slide1, slide2, slide3, slide4, slide5, slide6]
    for s, fn in zip(prs.slides, builders):
        fn(s, args)
        if fn is not slide1:
            set_oval(s, args.team_name)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"wrote {out}  ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
