/**
 * Frequency-decoupled learned odometry stand-in [F7].
 * Vehicle-motion power lives below 2 Hz (SNR +29 dB); above 10 Hz is vibration
 * (−34 dB). Low band → slow recurrence (velocity); high band → noise adapter.
 *
 * A full MambaIO/CNN-GRU trains in lab/models. This module is the ONNX-shaped
 * interface plus a physics-informed fallback that ships in the web demo.
 */

import type { ISensorFrame } from "../types/index.ts";
import { hypot3 } from "../math.ts";
import { windowForRate } from "../preprocess/index.ts";

export interface OdoEstimate {
  speed: number;
  speedVar: number;
  yawRate: number;
  accelFwd: number;
}

export class FrequencyDecoupledOdo {
  private buf: ISensorFrame[] = [];
  private hz: number;
  private win: number;
  private speed = 0;

  constructor(hz = 10) {
    this.hz = hz;
    this.win = windowForRate(hz, 2);
  }

  push(f: ISensorFrame): OdoEstimate {
    this.buf.push(f);
    if (this.buf.length > this.win) this.buf.shift();
    return this.infer();
  }

  infer(): OdoEstimate {
    const w = this.buf;
    if (w.length < 4) return { speed: this.speed, speedVar: 4, yawRate: 0, accelFwd: 0 };

    // High-band energy (vibration) vs low-band (motion). 10 Hz IO-VNBD:
    // consecutive differences ≈ high band; moving average ≈ low band.
    let lowAx = 0, lowAy = 0, highE = 0, yaw = 0;
    const n = w.length;
    for (let i = 0; i < n; i++) {
      const f = w[i]!;
      lowAx += f.ax;
      lowAy += f.ay;
      yaw += f.gz;
      if (i > 0) {
        const dax = f.ax - w[i - 1]!.ax;
        const day = f.ay - w[i - 1]!.ay;
        const daz = f.az - w[i - 1]!.az;
        highE += dax * dax + day * day + daz * daz;
      }
    }
    lowAx /= n;
    lowAy /= n;
    yaw /= n;
    const accelFwd = lowAx;
    const dt = 1 / this.hz;
    this.speed = Math.max(0, this.speed + accelFwd * dt);
    // Damp with specific-force consistency (won't work as AHRS; it's a prior).
    const aMean = w.reduce((s, f) => s + hypot3(f.ax, f.ay, f.az), 0) / n;
    if (aMean < 10.4 && Math.abs(yaw) < 0.05) {
      this.speed *= 0.995;
    }
    const highRms = Math.sqrt(highE / Math.max(1, n - 1));
    const speedVar = 0.4 + 3.2 * highRms;
    return { speed: this.speed, speedVar, yawRate: yaw, accelFwd };
  }

  setSpeed(v: number): void {
    this.speed = Math.max(0, v);
  }
}
