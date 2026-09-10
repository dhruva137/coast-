import { useEffect, useRef, useState } from "react";
import { LossChart, type LossChartHandle } from "./LossChart";
import {
  clearTrainOutput,
  downloadBlob,
  downloadJson,
  fetchMetrics,
  fetchTrainStatus,
  figureUrl,
  openTrainStream,
  startTrain,
  type LedgerRow,
  type MetricsPayload,
  type TrainEpoch,
  type TrainEvent,
} from "../lib/trainApi";

function dataUrlToBlob(dataUrl: string): Blob {
  const [head, body] = dataUrl.split(",");
  const mime = /data:([^;]+)/.exec(head ?? "")?.[1] ?? "image/png";
  const bin = atob(body ?? "");
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

export function TrainPanel() {
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [epochs, setEpochs] = useState<TrainEpoch[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [label, setLabel] = useState(
    "python -m lab.demo · IO-VNBD UK · real GPU/CPU train, not a fake curve"
  );
  const [error, setError] = useState<string | null>(null);
  const [figures, setFigures] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [rmse, setRmse] = useState<{ model: number; hold: number } | null>(null);
  const [holdBaseline, setHoldBaseline] = useState<number | null>(null);
  const [switchNote, setSwitchNote] = useState<string | null>(null);
  const chartRef = useRef<LossChartHandle>(null);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    fetchMetrics()
      .then(setMetrics)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    fetchTrainStatus()
      .then((s) => {
        setRunning(Boolean(s.running));
        if (s.epochs?.length) setEpochs(s.epochs);
        if (s.error) setError(s.error);
      })
      .catch(() => {
        /* API comes up with Vite */
      });
  }, []);

  useEffect(() => {
    const stop = openTrainStream((ev: TrainEvent) => {
      if (ev.type === "hello") {
        setRunning(Boolean(ev.running));
        if (typeof ev.label === "string") setLabel(ev.label);
        return;
      }
      if (ev.type === "line" && typeof ev.text === "string") {
        setLog((prev) => [...prev.slice(-80), ev.text]);
        return;
      }
      if (ev.type === "train_baselines") {
        const hb = Number(ev.hold_baseline_rmse);
        if (Number.isFinite(hb)) setHoldBaseline(hb);
        return;
      }
      if (ev.type === "objective_switch") {
        setSwitchNote(String(ev.label ?? "MSE → NLL"));
        return;
      }
      if (ev.type === "epoch") {
        const row = ev as TrainEpoch & { type: "epoch" };
        if (row.hold_baseline_rmse != null && Number.isFinite(row.hold_baseline_rmse)) {
          setHoldBaseline(row.hold_baseline_rmse);
        }
        setEpochs((prev) => {
          const next = prev.filter((e) => e.epoch !== row.epoch);
          next.push(row);
          next.sort((a, b) => a.epoch - b.epoch);
          return next;
        });
        setRunning(true);
        return;
      }
      if (ev.type === "rmse") {
        setRmse({ model: Number(ev.model_rmse), hold: Number(ev.hold_rmse) });
        if (Number.isFinite(Number(ev.hold_rmse))) setHoldBaseline(Number(ev.hold_rmse));
        return;
      }
      if (ev.type === "done") {
        setRunning(false);
        setBusy(false);
        if (Array.isArray(ev.figures)) setFigures(ev.figures);
        fetchMetrics().then(setMetrics).catch(() => undefined);
        return;
      }
      if (ev.type === "error") {
        setRunning(false);
        setBusy(false);
        setError(String(ev.error ?? "train failed"));
      }
    });
    return stop;
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  async function onTrain() {
    setError(null);
    setBusy(true);
    setEpochs([]);
    setLog([]);
    setRmse(null);
    setHoldBaseline(null);
    setSwitchNote(null);
    setFigures([]);
    try {
      const res = await startTrain();
      if (!res.ok) {
        setError(res.error ?? "could not start train");
        setBusy(false);
        return;
      }
      setRunning(true);
      if (res.label) setLabel(res.label);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  async function onClear() {
    if (running) {
      setError("Stop the run first — output is still being written.");
      return;
    }
    try {
      const res = await clearTrainOutput();
      if (!res.ok) {
        setError(res.error ?? "clear failed");
        return;
      }
      setFigures([]);
      setEpochs([]);
      setLog((prev) => [...prev, `cleared demo output: ${(res.deleted ?? []).join(", ") || "nothing"}`]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onSave() {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadJson(`coast-train-${stamp}.json`, {
      saved_utc: new Date().toISOString(),
      label,
      epochs,
      rmse,
      hold_baseline_rmse: holdBaseline,
      switch_note: switchNote,
      figures,
      honesty: metrics?.honesty,
      ledger: metrics?.ledger,
      note: "Live session from python -m lab.demo. Headline 2.02× lower median position error cites committed mapfilter, not this quick run.",
    });
    const png = chartRef.current?.toPng();
    if (png) downloadBlob(`coast-loss-${stamp}.png`, dataUrlToBlob(png));
    for (const name of figures) {
      try {
        const res = await fetch(figureUrl(name));
        if (!res.ok) continue;
        downloadBlob(name, await res.blob());
      } catch {
        /* skip missing figure */
      }
    }
  }

  const last = epochs[epochs.length - 1];
  const heldRmse = last?.held_rmse ?? last?.rmse;
  const objective = (last?.objective || last?.mode || "—").toString().toUpperCase();

  return (
    <div className="train-panel">
      <p className="train-honest">{label}</p>
      <div className="train-actions">
        <button className="go" type="button" disabled={running || busy} onClick={() => void onTrain()}>
          {running || busy ? "Training…" : "Train live"}
        </button>
        <button className="pill btn-like" type="button" onClick={() => void onSave()} disabled={!epochs.length && !figures.length}>
          Save graphs
        </button>
        <button className="pill btn-like" type="button" onClick={() => void onClear()} disabled={running}>
          Clear demo output
        </button>
      </div>
      <div className="train-kpis">
        <div>
          <span>held RMSE</span>
          <b>{heldRmse != null ? `${heldRmse.toFixed(3)} m/s` : rmse ? `${rmse.model.toFixed(3)}` : "—"}</b>
        </div>
        <div>
          <span>hold baseline</span>
          <b>{holdBaseline != null ? `${holdBaseline.toFixed(3)} m/s` : rmse ? `${rmse.hold.toFixed(3)}` : "—"}</b>
        </div>
        <div>
          <span>objective</span>
          <b>{last ? objective : "—"}{switchNote ? ` · ${switchNote}` : ""}</b>
        </div>
        <div>
          <span>epoch</span>
          <b>{last ? `${last.epoch}/${last.epochs}` : "—"}</b>
        </div>
        <div>
          <span>train loss</span>
          <b>{last ? `${last.loss.toFixed(4)} (${objective})` : "—"}</b>
        </div>
        <div>
          <span>σ mean</span>
          <b>{last?.sigma_mean != null ? last.sigma_mean.toFixed(3) : "—"}</b>
        </div>
      </div>
      <LossChart ref={chartRef} epochs={epochs} holdBaselineRmse={holdBaseline} />
      {error && <p className="train-error">{error}</p>}
      <pre className="train-log" ref={logRef}>
        {log.length ? log.join("\n") : "stdout from lab.demo will stream here."}
      </pre>
      {figures.length > 0 && (
        <div className="train-figs">
          {figures.map((name) => (
            <figure key={name}>
              <img src={figureUrl(name)} alt={name} />
              <figcaption>{name}</figcaption>
            </figure>
          ))}
        </div>
      )}
      {metrics && (
        <div className="train-ledger">
          <h2>Measured ledger — not this quick run</h2>
          {metrics.report_error ? (
            <p className="train-error">{metrics.report_error}</p>
          ) : (
            <ul>
              {metrics.ledger.map((row: LedgerRow) => (
                <li key={`${row.component}-${row.metric}`}>
                  <strong>{row.display}</strong>
                  <em>{row.component}</em>
                  <span>{row.source}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="fine">{metrics.honesty}</p>
        </div>
      )}
    </div>
  );
}
