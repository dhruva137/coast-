/** Instrument-panel number formatters. IBM Plex Mono on the other side of these. */

const EM = "—";

function finite(n: number): boolean {
  return typeof n === "number" && Number.isFinite(n);
}

function places(n: number, digits: number): string {
  return n.toFixed(digits);
}

/** Metres. Example formats only. claims:ignore */
export function fmtM(metres: number, digits = 1): string {
  if (!finite(metres)) return EM;
  return `${places(metres, digits)} m`;
}

/** Percentage points already in %. Example formats only. claims:ignore */
export function fmtPct(pct: number, digits = 2): string {
  if (!finite(pct)) return EM;
  return `${places(pct, digits)}%`;
}

/** Hertz. Example formats only. claims:ignore */
export function fmtHz(hz: number, digits = 1): string {
  if (!finite(hz)) return EM;
  return `${places(hz, digits)} Hz`;
}

/** Degrees. Minus is U+2212. `−12.4°`. */
export function fmtDeg(deg: number, digits = 1): string {
  if (!finite(deg)) return EM;
  const abs = places(Math.abs(deg), digits);
  if (deg < 0) return `−${abs}°`;
  if (deg > 0) return `+${abs}°`;
  return `${places(0, digits)}°`;
}

/** WGS84 pair for a judge readout. `12.991200°N  77.552300°E`. */
export function fmtLatLon(lat: number, lon: number, digits = 6): string {
  if (!finite(lat) || !finite(lon)) return EM;
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${places(Math.abs(lat), digits)}°${ns}  ${places(Math.abs(lon), digits)}°${ew}`;
}
