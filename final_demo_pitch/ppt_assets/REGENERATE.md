# PPT regeneration

There is **no** existing `python-pptx` build script in this repo.
`COAST_SIH2026_IDEA.pptx` is the official SIH IDEA template paste target.

## After editing `slide_*.md`

1. Paste each slide’s **Conclusion headline** as the largest title on that slide.
2. Place the listed **Dominant visual** only (cut competing graphics).
3. Keep body ≥18 pt.
4. Insert money visual from:
   - `final_demo_pitch/ppt_assets/diagrams/money_shot.png`
   - animated: `money_shot.gif` (and `money_shot.mp4` when present)
5. Regenerate money visual:
   ```bash
   python -m lab.eval.money_shot
   ```
6. Lint claims after paste:
   ```bash
   python tools/verify_claims.py
   ```

Wording lock: **2.02×** only for **median position error** (mapfilter junctions), never as a drift-% ratio.
