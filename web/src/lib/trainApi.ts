export type TrainEpoch = {
  epoch: number;
  epochs: number;
  loss: number;
  /** Held-out RMSE (m/s) — headline task metric. */
  rmse?: number;
  held_rmse?: number;
  hold_baseline_rmse?: number;
  sigma_mean?: number;
  sigma_median?: number;
  cl_end_err_m?: number;
  /** Objective phase: MSE | NLL (alias of objective). */
  mode?: string;
  objective?: string;
  elapsed_s?: number;
  source?: string;
};

export type TrainEvent =
  | { type: "hello"; running?: boolean; label?: string }
  | ({ type: "epoch" } & TrainEpoch)
  | { type: "line"; text: string }
  | { type: "rmse"; model_rmse: number; hold_rmse: number; seconds: number; source?: string }
  | {
      type: "train_baselines";
      hold_baseline_rmse?: number;
      warmup_epochs_mse?: number;
      nll_from_epoch?: number;
      held?: string;
      note?: string;
    }
  | {
      type: "objective_switch";
      from?: string;
      to?: string;
      at_epoch?: number;
      label?: string;
      note?: string;
    }
  | { type: "done"; returncode: number; figures?: string[]; label?: string }
  | { type: "error"; error: string }
  | { type: string; [k: string]: unknown };

export type LedgerRow = {
  component: string;
  metric: string;
  value: number;
  display: string;
  source: string;
  note: string;
};

export type MetricsPayload = {
  ledger: LedgerRow[];
  story: string;
  honesty: string;
  figures: string[];
  report_error?: string | null;
};

export type TrainStart = {
  ok: boolean;
  error?: string;
  pid?: number;
  cmd?: string[];
  label?: string;
  note?: string;
};

export function figureUrl(name: string): string {
  return `/api/figures/${encodeURIComponent(name)}?t=${Date.now()}`;
}

export async function startTrain(): Promise<TrainStart> {
  const res = await fetch("/api/train", { method: "POST" });
  return (await res.json()) as TrainStart;
}

export async function clearTrainOutput(): Promise<{ ok: boolean; deleted?: string[]; error?: string }> {
  const res = await fetch("/api/train/clear", { method: "POST" });
  return (await res.json()) as { ok: boolean; deleted?: string[]; error?: string };
}

export async function fetchMetrics(): Promise<MetricsPayload> {
  const res = await fetch("/api/metrics");
  if (!res.ok) throw new Error(`metrics ${res.status}`);
  return (await res.json()) as MetricsPayload;
}

export async function fetchTrainStatus(): Promise<{
  running: boolean;
  epochs: TrainEpoch[];
  last_line?: string | null;
  mode?: string;
  error?: string | null;
  figures?: string[];
}> {
  const res = await fetch("/api/train/status");
  return (await res.json()) as {
    running: boolean;
    epochs: TrainEpoch[];
    last_line?: string | null;
    mode?: string;
    error?: string | null;
    figures?: string[];
  };
}

export function openTrainStream(onEvent: (ev: TrainEvent) => void): () => void {
  const es = new EventSource("/api/train/stream");
  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as TrainEvent);
    } catch {
      /* ignore malformed */
    }
  };
  es.onerror = () => {
    /* EventSource retries; leave open until caller closes */
  };
  return () => es.close();
}

export function downloadBlob(filename: string, blob: Blob): void {
  const a = document.createElement("a");
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(filename: string, data: unknown): void {
  downloadBlob(filename, new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
}
