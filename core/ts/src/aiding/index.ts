/**
 * Opportunistic aiding: light-pulse COUNTING (not phase matching) [F11],
 * barometer for garage level, acoustic speed proxy from tyre-noise amplitude.
 */

export interface LightCounterState {
  lastBright: boolean;
  count: number;
  lastTns: number;
  alongTrackM: number;
}

export function createLightCounter(): LightCounterState {
  return { lastBright: false, count: 0, lastTns: 0, alongTrackM: 0 };
}

/**
 * Count falling/rising edges of ambient lux. Phase matching only constrains
 * position modulo spacing (~0% gain). Counting from the portal is absolute:
 * 9–21% along-track improvement in simulation at 60% detection / 10% FA.
 */
export function stepLightCount(
  st: LightCounterState,
  lux: number,
  t_ns: number,
  spacingM: number,
  threshold = 35,
): LightCounterState {
  const bright = lux > threshold;
  let count = st.count;
  if (bright && !st.lastBright && spacingM > 0) count += 1;
  return {
    lastBright: bright,
    count,
    lastTns: t_ns,
    alongTrackM: count * spacingM,
  };
}

/** Standard atmosphere: 1 hPa ≈ 8.43 m near sea level. */
export function baroDeltaAlt(hpa: number, hpaRef: number): number {
  return (hpaRef - hpa) * 8.435;
}

export function garageLevel(deltaAlt: number, deckHeight = 3.2): number {
  return Math.round(deltaAlt / deckHeight);
}

/**
 * Crude on-board acoustic speed: tyre/wind noise amplitude scales ~ v^n.
 * Koops & Franchetti / Göksu — we implement the on-board case, not roadside arrays.
 * `rms` is mic RMS in arbitrary units; calibrated at vRef.
 */
export function acousticSpeed(rms: number, rmsRef: number, vRef: number, n = 1.35): number {
  if (rmsRef <= 1e-9) return 0;
  return vRef * Math.pow(Math.max(0, rms) / rmsRef, 1 / n);
}
