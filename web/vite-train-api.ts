import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { IncomingMessage, ServerResponse } from "node:http";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Connect, Plugin, ViteDevServer } from "vite";

const dir = fileURLToPath(new URL(".", import.meta.url));
const REPO = resolve(dir, "..");
const FIGURES = join(REPO, "figures");
const MAPFILTER = join(REPO, "lab/stress/results/mapfilter/report.json");
const ISRO_REPORT = join(REPO, "lab/stress/results/isro_benchmark/report.json");
const HEADING_REPORT = join(REPO, "lab/stress/results/heading_ablation/report.json");
const MAPFILTER_SUMMARY = "lab/stress/results/mapfilter/summary.md";
const ISRO_SUMMARY = "lab/stress/results/isro_benchmark/summary.md";
const HEADING_SUMMARY = "lab/stress/results/heading_ablation/summary.md";

const EPOCH_RE =
  /epoch\s+(\d+)\s*\/\s*(\d+)\s+loss=([0-9.eE+-]+)(?:\s+rmse=([0-9.eE+-]+))?\s+\((\w+)\)\s+([0-9.]+)s/i;
const RMSE_RE = /quick RMSE model=([0-9.eE+-]+)\s+hold=([0-9.eE+-]+)\s+\(([0-9.]+)s\)/i;

type TrainEvent = Record<string, unknown>;

function resolvePython(): string {
  return process.env.COAST_PYTHON || process.env.PYTHON || "python";
}

const subscribers = new Set<ServerResponse>();
const history: TrainEvent[] = [];
let proc: ChildProcessWithoutNullStreams | null = null;
const status: {
  running: boolean;
  pid: number | null;
  started_at: number | null;
  finished_at: number | null;
  returncode: number | null;
  mode: string;
  label: string;
  epochs: TrainEvent[];
  last_line: string | null;
  error: string | null;
} = {
  running: false,
  pid: null,
  started_at: null,
  finished_at: null,
  returncode: null,
  mode: "idle",
  label: "fast re-run (python -m lab.demo) — full 2.02× lower median position error cites mapfilter",
  epochs: [],
  last_line: null,
  error: null,
};

function listFigures(): string[] {
  if (!existsSync(FIGURES)) return [];
  return ["drift_comparison.png", "cdf_error.png", "trajectory_overlay.png"].filter((n) =>
    existsSync(join(FIGURES, n)),
  );
}

function broadcast(event: TrainEvent): void {
  history.push(event);
  if (history.length > 2000) history.splice(0, 500);
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  for (const res of [...subscribers]) {
    try {
      res.write(payload);
    } catch {
      subscribers.delete(res);
    }
  }
}

function parseLine(line: string): TrainEvent[] {
  const trimmed = line.replace(/\r$/, "");
  const events: TrainEvent[] = [{ type: "line", text: trimmed }];
  const jsonMark = "COAST_EVENT ";
  const idx = trimmed.indexOf(jsonMark);
  if (idx >= 0) {
    try {
      const ev = JSON.parse(trimmed.slice(idx + jsonMark.length)) as TrainEvent;
      if (ev.type === "epoch") {
        status.epochs.push(ev);
        status.last_line = trimmed;
      }
      events.push(ev);
      return events;
    } catch {
      /* fall through to regex */
    }
  }
  const m = EPOCH_RE.exec(trimmed);
  if (m) {
    const ev: TrainEvent = {
      type: "epoch",
      epoch: Number(m[1]),
      epochs: Number(m[2]),
      loss: Number(m[3]),
      rmse: m[4] != null ? Number(m[4]) : undefined,
      mode: m[5],
      elapsed_s: Number(m[6]),
      source: "lab.demo stdout",
    };
    status.epochs.push(ev);
    status.last_line = trimmed;
    events.push(ev);
    return events;
  }
  const m2 = RMSE_RE.exec(trimmed);
  if (m2) {
    events.push({
      type: "rmse",
      model_rmse: Number(m2[1]),
      hold_rmse: Number(m2[2]),
      seconds: Number(m2[3]),
      source: "lab.demo stdout",
    });
  }
  status.last_line = trimmed;
  return events;
}

function startTrain(): { ok: boolean; error?: string; pid?: number; cmd?: string[]; label?: string; note?: string } {
  if (proc && proc.exitCode == null) {
    return { ok: false, error: "training already running", pid: proc.pid };
  }
  history.length = 0;
  status.running = true;
  status.started_at = Date.now() / 1000;
  status.finished_at = null;
  status.returncode = null;
  status.mode = "quick";
  status.epochs = [];
  status.last_line = null;
  status.error = null;
  status.label =
    "fast re-run (python -m lab.demo) — full 2.02× lower median position error cites lab/stress/results/mapfilter/summary.md";

  const python = resolvePython();
  const cmd = [python, "-u", "-m", "lab.demo"];
  try {
    proc = spawn(cmd[0]!, cmd.slice(1), {
      cwd: REPO,
      env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    status.running = false;
    status.error = e instanceof Error ? e.message : String(e);
    status.mode = "error";
    return { ok: false, error: status.error };
  }
  status.pid = proc.pid ?? null;
  let buf = "";
  const onChunk = (chunk: Buffer | string) => {
    buf += typeof chunk === "string" ? chunk : chunk.toString("utf8");
    const parts = buf.split(/\n/);
    buf = parts.pop() ?? "";
    for (const line of parts) {
      for (const ev of parseLine(line)) broadcast(ev);
    }
  };
  proc.stdout.on("data", onChunk);
  proc.stderr.on("data", onChunk);
  proc.on("close", (code) => {
    if (buf.trim()) {
      for (const ev of parseLine(buf)) broadcast(ev);
      buf = "";
    }
    status.running = false;
    status.finished_at = Date.now() / 1000;
    status.returncode = code;
    status.mode = code === 0 ? "done" : "failed";
    proc = null;
    broadcast({ type: "done", returncode: code, figures: listFigures(), label: status.label });
  });
  proc.on("error", (err) => {
    status.running = false;
    status.error = err.message;
    status.mode = "error";
    proc = null;
    broadcast({ type: "error", error: err.message });
  });
  return {
    ok: true,
    pid: status.pid ?? undefined,
    cmd,
    label: status.label,
    note: "This is a fast re-run of the training path. Headline 2.02× lower median position error cites committed mapfilter results, not this short session.",
  };
}

function clearDemo(): { ok: boolean; deleted: string[]; error?: string } {
  if (status.running) return { ok: false, deleted: [], error: "training still running" };
  const deleted: string[] = [];
  if (!existsSync(FIGURES)) return { ok: true, deleted };
  for (const name of readdirSync(FIGURES)) {
    if (name === "_reference") continue;
    const p = join(FIGURES, name);
    if (!statSync(p).isFile()) continue;
    if (name.endsWith(".png") || name === "demo_run.json") {
      unlinkSync(p);
      deleted.push(name);
    }
  }
  return { ok: true, deleted };
}

function bestIsroArmPct(isro: { summary: Record<string, { pass_rate: number }> }, arm: string): number {
  const rates = Object.entries(isro.summary)
    .filter(([k]) => k.startsWith(`${arm}/`))
    .map(([, v]) => v.pass_rate);
  if (!rates.length) throw new Error(`no ${arm} rows`);
  return Math.round(Math.max(...rates) * 100);
}

function loadMetrics(): Record<string, unknown> {
  let reportErr: string | null = null;
  try {
    const report = JSON.parse(readFileSync(MAPFILTER, "utf8")) as {
      scenarios: {
        junctions: {
          free_median_error_m: number;
          pf_median_error_m: number;
          free_median_drift_pct: number;
          pf_median_drift_pct: number;
          improvement_x: number;
          free_pass: number;
          pf_pass: number;
          n: number;
        };
      };
    };
    const junc = report.scenarios.junctions;
    const freeErr = junc.free_median_error_m;
    const coastErr = junc.pf_median_error_m;
    const freeDrift = junc.free_median_drift_pct;
    const coastDrift = junc.pf_median_drift_pct;
    const improvementX = junc.improvement_x;
    const freePass = junc.free_pass;
    const pfPass = junc.pf_pass;
    const nOutages = junc.n;

    const ledger: Record<string, unknown>[] = [
      {
        component: "Free DR (junctions / open road)",
        metric: "median position error",
        value: freeErr,
        display: `${freeErr.toFixed(2)} m`,
        source: MAPFILTER_SUMMARY,
        note: `Measured on ${nOutages} outages; CAN ground truth.`,
      },
      {
        component: "+ Map-in-loop particle filter (COAST)",
        metric: "median position error",
        value: coastErr,
        display: `${coastErr.toFixed(2)} m  (${improvementX.toFixed(2)}× lower median position error)`,
        source: MAPFILTER_SUMMARY,
        note: `Pass ${freePass}->${pfPass} of ${nOutages}. Full committed run — not the browser fast re-run. 2.02× is median position error, not drift %.`,
      },
      {
        component: "Free DR → COAST (junctions)",
        metric: "median drift %",
        value: coastDrift,
        display: `${freeDrift.toFixed(2)}% → ${coastDrift.toFixed(2)}%`,
        source: MAPFILTER_SUMMARY,
        note: "Drift % is a separate quantity from the 2.02× position-error ratio. No multiplier on this row.",
      },
    ];

    try {
      const heading = JSON.parse(readFileSync(HEADING_REPORT, "utf8")) as {
        aggregate: { F_oracle: { pass_isro: number; n_rows: number } };
      };
      const oracle = heading.aggregate.F_oracle;
      const oraclePass = oracle.pass_isro;
      const oracleN = oracle.n_rows;
      const oracleFailPct = Math.round(100 * (1 - oraclePass / oracleN));
      ledger.push({
        component: "Perfect gyro still fails (heading ceiling)",
        metric: "fail rate @ 60 s (oracle yaw)",
        value: oracleFailPct,
        display: `${oracleFailPct}% fail (${oraclePass}/${oracleN} pass)`,
        source: HEADING_SUMMARY,
        note: "Why the map sits inside the loop.",
      });
    } catch (e) {
      ledger.push({
        component: "Perfect gyro still fails (heading ceiling)",
        metric: "fail rate @ 60 s (oracle yaw)",
        value: 0,
        display: "unavailable",
        source: HEADING_SUMMARY,
        note: `Could not read heading_ablation/report.json: ${e instanceof Error ? e.message : String(e)}`,
      });
    }

    let shortPct: number | null = null;
    let tunnelPct: number | null = null;
    try {
      const isro = JSON.parse(readFileSync(ISRO_REPORT, "utf8")) as {
        summary: Record<string, { pass_rate: number }>;
      };
      shortPct = bestIsroArmPct(isro, "ARM_SHORT");
      tunnelPct = bestIsroArmPct(isro, "ARM_TUNNEL");
      ledger.push({
        component: "ISRO free-DR short arm",
        metric: "pass rate",
        value: shortPct,
        display: `${shortPct}%`,
        source: ISRO_SUMMARY,
        note: "Best free-DR method on ARM_SHORT (from isro_benchmark/report.json).",
      });
      ledger.push({
        component: "ISRO free-DR tunnel arm / ISRO bar",
        metric: "pass rate / drift bar",
        value: tunnelPct,
        display: `${tunnelPct}%`,
        source: ISRO_SUMMARY,
        note: "Best free-DR method on ARM_TUNNEL; problem statement drift bar is 10%.",
      });
    } catch (e) {
      ledger.push({
        component: "ISRO free-DR arms",
        metric: "pass rate",
        value: 0,
        display: "unavailable",
        source: ISRO_SUMMARY,
        note: `Could not read isro_benchmark/report.json: ${e instanceof Error ? e.message : String(e)}`,
      });
    }

    return {
      ledger,
      story: `${improvementX.toFixed(2)}× lower median position error (${freeErr.toFixed(2)} m → ${coastErr.toFixed(2)} m); median drift ${freeDrift.toFixed(2)}% → ${coastDrift.toFixed(2)}%; perfect gyro fails ~55%; ISRO free-DR arms ${shortPct ?? "?"}%/${tunnelPct ?? "?"}%`,
      honesty:
        "Console Train = python -m lab.demo (quick AVNet + figure regen). It does not re-score the full map-in-loop suite. Cite 2.02× lower median position error from lab/stress/results/mapfilter/summary.md.",
      figures: listFigures(),
      report_error: reportErr,
    };
  } catch {
    reportErr =
      "Could not read lab/stress/results/mapfilter/report.json — no measured numbers to show.";
    return {
      ledger: [],
      story: "",
      honesty:
        "Console Train = python -m lab.demo (quick AVNet + figure regen). Measured ledger requires lab/stress/results/mapfilter/report.json.",
      figures: listFigures(),
      report_error: reportErr,
    };
  }
}

function json(res: ServerResponse, code: number, obj: unknown): void {
  const body = Buffer.from(JSON.stringify(obj), "utf8");
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": body.length,
  });
  res.end(body);
}

function sse(req: IncomingMessage, res: ServerResponse): void {
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  res.write(`data: ${JSON.stringify({ type: "hello", running: status.running, label: status.label })}\n\n`);
  for (const ev of history.slice(-200)) {
    res.write(`data: ${JSON.stringify(ev)}\n\n`);
  }
  subscribers.add(res);
  const ping = setInterval(() => {
    try {
      res.write(": keepalive\n\n");
    } catch {
      clearInterval(ping);
      subscribers.delete(res);
    }
  }, 15000);
  req.on("close", () => {
    clearInterval(ping);
    subscribers.delete(res);
  });
}

function serveFigure(name: string, res: ServerResponse): void {
  if (!name || name.includes("/") || name.includes("\\") || name.includes("..")) {
    res.writeHead(400);
    res.end("bad name");
    return;
  }
  const fp = join(FIGURES, name);
  if (!existsSync(fp) || !statSync(fp).isFile()) {
    res.writeHead(404);
    res.end("not found");
    return;
  }
  const resolved = resolve(fp);
  if (relative(FIGURES, resolved).startsWith("..")) {
    res.writeHead(400);
    res.end("bad name");
    return;
  }
  const data = readFileSync(fp);
  const ctype = name.endsWith(".json") ? "application/json" : "image/png";
  res.writeHead(200, {
    "Content-Type": ctype,
    "Content-Length": data.length,
    "Cache-Control": "no-cache",
  });
  res.end(data);
}

function attach(middlewares: Connect.Server): void {
  middlewares.use((req, res, next) => {
    const url = (req.url ?? "").split("?")[0] ?? "";
    if (!url.startsWith("/api/")) {
      next();
      return;
    }
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      });
      res.end();
      return;
    }
    if (req.method === "POST" && url === "/api/train") {
      const result = startTrain();
      json(res, result.ok ? 200 : 409, result);
      return;
    }
    if (req.method === "POST" && url === "/api/train/clear") {
      json(res, 200, clearDemo());
      return;
    }
    if (req.method === "GET" && url === "/api/train/stream") {
      sse(req, res);
      return;
    }
    if (req.method === "GET" && url === "/api/train/status") {
      json(res, 200, { ...status, figures: listFigures() });
      return;
    }
    if (req.method === "GET" && url === "/api/metrics") {
      json(res, 200, loadMetrics());
      return;
    }
    if (req.method === "GET" && url.startsWith("/api/figures/")) {
      serveFigure(decodeURIComponent(url.slice("/api/figures/".length)), res);
      return;
    }
    res.writeHead(404);
    res.end("not found");
  });
}

export function coastTrainPlugin(): Plugin {
  return {
    name: "coast-train-api",
    configureServer(server: ViteDevServer) {
      attach(server.middlewares);
      const close = () => {
        if (proc && proc.exitCode == null) proc.kill();
      };
      server.httpServer?.on("close", close);
    },
  };
}
