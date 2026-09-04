# SIH 26168 — current progress

**Updated:** 4 Sep 2026 (finals eng finish + push)  
**Repo:** https://github.com/dhruva137/SIH-2026

## One-line status

Finals pack + closed-loop AVNet + **leave-file-out** protocol shipped. Mid-route 60 s road-speed: **0 PASS_ISRO** (honest). Winning path = own RED + improve heading/map priors — never fake GREEN.

## Credibility rule

Judges destroy teams that claim “proven / first-try perfect APK accuracy” without measured rows.  
Every cross-question lives in `docs/JUDGE_CROSS_EXAM.md` with **file pointers**, including failures.

## Shipped this push

| Artifact | Role |
|---|---|
| `docs/FINALS_WINNER_ARCHITECTURE.md` | Finals stack + novelty |
| `docs/JUDGE_CROSS_EXAM.md` | 25 hostile Q&As |
| `docs/PAPER_NOVELTY.md` | Defensible abstract claims |
| `lab/stress/avnet_closed_loop.py` | Wire trained weights into DR |
| `lab/stress/run_avnet_closed_loop.py` | Closed-loop score table |
| `lab/stress/run_leave_file_out.py` | Paper leave-file-out protocol |
| `lab/stress/map_aid.py` `dead_reckon_arclength` | Known-corridor product mode |
| `lab/models/train_avnet.py` `--exclude` | Hold-out training |
| `lab/stress/results/avnet_closed_loop/` | Wired maximize → ISRO scores |
| `lab/stress/results/leave_file_out/` | No train/eval leakage table |

## Measured (honest)

| Protocol | PASS_ISRO |
|---|---|
| Closed-loop AVNet mid 60 s | **0** |
| Leave-file-out AVNet mid 60 s | **0** |
| Arclength known-route mid 60 s | **0** |

S-S1 LFO: `avnet_speed` 182.9 m vs `car_bias` 185.5 m — tiny improvement, still FAIL the bar.

## Still true

| Gate | Colour |
|---|---|
| Alignment | GREEN |
| Proposal IO-VNBD plots | GREEN |
| Prototype gate | PASS (≠ ISRO) |
| Open-loop / closed-loop ISRO road-speed | **RED** |
| Real two-wheeler field | **RED** |

## Next (post-push)

1. Better heading prior (mount-cal + longer seed bias) — speed is not the only killer.  
2. OSM / local corridor PF (not whole-drive snap).  
3. Port map-aid into Android NAVIGATE as **method demo** only until green rows exist.  
4. Optional scooter KEEP logs for lean novelty.
