/**
 * Preprocess: resample, 2nd-order Butterworth, static bias cal, ZUPT / ZIHR.
 * Designed for 10 Hz IO-VNBD AND 50–200 Hz phone IMU. Window math is rate-aware.
 */

import type { ISensorFrame } from "../types/index.ts";
import { hypot3 } from "../math.ts";

export interface Calib {
  ba: [number, number, number];
  bg: [number, number, number];
  samples: number;
}

export function butter2Lowpass(fc: number, fs: number): { a: [number, number]; b: [number, number, number] } {
  const k = Math.tan((Math.PI * fc) / fs);
  const k2 = k * k;
  const n = 1 + Math.SQRT2 * k + k2;
  const b0 = k2 / n;
  const b1 = 2 * b0;
  const b2 = b0;
  const a1 = (2 * (k2 - 1)) / n;
  const a2 = (1 - Math.SQRT2 * k + k2) / n;
  return { a: [a1, a2], b: [b0, b1, b2] };
}

export class Iir2 {
  private x1 = 0;
  private x2 = 0;
  private y1 = 0;
  private y2 = 0;
  constructor(private readonly c: { a: [number, number]; b: [number, number, number] }) {}
  step(x: number): number {
    const { a, b } = this.c;
    const y = b[0] * x + b[1] * this.x1 + b[2] * this.x2 - a[0] * this.y1 - a[1] * this.y2;
    this.x2 = this.x1;
    this.x1 = x;
    this.y2 = this.y1;
    this.y1 = y;
    return y;
  }
  reset(): void {
    this.x1 = this.x2 = this.y1 = this.y2 = 0;
  }
}

export class SixAxisFilter {
  private axes: Iir2[];
  constructor(fc: number, fs: number) {
    const c = butter2Lowpass(fc, fs);
    this.axes = Array.from({ length: 6 }, () => new Iir2(c));
  }
  apply(f: ISensorFrame): ISensorFrame {
    return {
      ...f,
      ax: this.axes[0]!.step(f.ax),
      ay: this.axes[1]!.step(f.ay),
      az: this.axes[2]!.step(f.az),
      gx: this.axes[3]!.step(f.gx),
      gy: this.axes[4]!.step(f.gy),
      gz: this.axes[5]!.step(f.gz),
    };
  }
}

/** Detect still: |ω| small and |a| ≈ g. */
export function isStatic(f: ISensorFrame, g = 9.80665): boolean {
  const w = hypot3(f.gx, f.gy, f.gz);
  const a = hypot3(f.ax, f.ay, f.az);
  return w < 0.04 && Math.abs(a - g) < 0.35;
}

export class BiasCalibrator {
  private n = 0;
  private sa = [0, 0, 0];
  private sg = [0, 0, 0];
  private frozen: Calib | null = null;

  observe(f: ISensorFrame): void {
    if (this.frozen || !isStatic(f)) return;
    this.n += 1;
    this.sa[0] += f.ax;
    this.sa[1] += f.ay;
    this.sa[2] += f.az - 9.80665;
    this.sg[0] += f.gx;
    this.sg[1] += f.gy;
    this.sg[2] += f.gz;
    if (this.n >= 40) {
      this.frozen = {
        ba: [this.sa[0]! / this.n, this.sa[1]! / this.n, this.sa[2]! / this.n],
        bg: [this.sg[0]! / this.n, this.sg[1]! / this.n, this.sg[2]! / this.n],
        samples: this.n,
      };
    }
  }

  get(): Calib {
    return this.frozen ?? { ba: [0, 0, 0], bg: [0, 0, 0], samples: this.n };
  }

  apply(f: ISensorFrame): ISensorFrame {
    const c = this.get();
    return {
      ...f,
      ax: f.ax - c.ba[0],
      ay: f.ay - c.ba[1],
      az: f.az - c.ba[2],
      gx: f.gx - c.bg[0],
      gy: f.gy - c.bg[1],
      gz: f.gz - c.bg[2],
    };
  }
}

export function zupt(f: ISensorFrame): boolean {
  return isStatic(f);
}

/** Zero Integrated Heading Rate: freeze yaw while static. */
export function zihr(f: ISensorFrame): boolean {
  return hypot3(f.gx, f.gy, f.gz) < 0.03 && hypot3(f.ax, f.ay, f.az - 9.80665) < 0.4;
}

export function resampleLinear(frames: ISensorFrame[], hz: number): ISensorFrame[] {
  if (frames.length < 2) return frames.slice();
  const t0 = frames[0]!.t_ns;
  const t1 = frames[frames.length - 1]!.t_ns;
  const dt = 1e9 / hz;
  const out: ISensorFrame[] = [];
  let j = 0;
  for (let t = t0; t <= t1; t += dt) {
    while (j + 1 < frames.length && frames[j + 1]!.t_ns < t) j += 1;
    const a = frames[j]!;
    const b = frames[Math.min(j + 1, frames.length - 1)]!;
    const span = Math.max(1, b.t_ns - a.t_ns);
    const u = (t - a.t_ns) / span;
    const lerp = (x: number, y: number) => x + (y - x) * u;
    out.push({
      t_ns: t,
      ax: lerp(a.ax, b.ax),
      ay: lerp(a.ay, b.ay),
      az: lerp(a.az, b.az),
      gx: lerp(a.gx, b.gx),
      gy: lerp(a.gy, b.gy),
      gz: lerp(a.gz, b.gz),
      mx: lerp(a.mx, b.mx),
      my: lerp(a.my, b.my),
      mz: lerp(a.mz, b.mz),
      pressure_hpa: lerp(a.pressure_hpa, b.pressure_hpa),
      lux: lerp(a.lux, b.lux),
    });
  }
  return out;
}

/**
 * IO-VNBD is 10 Hz. AVNet windows of 200 samples at 200 Hz → 1 s are WRONG here.
 * At 10 Hz, a 1 s window is 10 samples. We use 2 s (20 samples) as the default
 * learned-odometry window.
 */
export function windowForRate(hz: number, seconds = 2): number {
  return Math.max(4, Math.round(hz * seconds));
}
