# Hugging Face upload — residual speed ONNX (7-channel)

When `lab/models/weights/avnet_residual.onnx` is present (exported after a
residual-speed training run), upload it as a model repo artifact. Do **not**
invent metrics in the model card; cite the measured summary only.

## What the file is

- **ONNX residual-on-persistence speed head** for COAST / PS 26168.
- **Input:** 7 channels — 6 IMU (accel + gyro window) **plus** previous speed
  `v_prev` as the 7th channel. The network predicts Δ̂ so
  `v̂ = v_prev + Δ̂`.
- **Not** the absolute 6-channel AVNet that loses to persistence on leave-file-out.

## Metrics (do not invent)

Point reviewers at the measured report:

- `lab/models/results/residual_speed/summary.md`
- `lab/models/results/residual_speed/report.json`

If those files are missing or still smoke-scale, say so — do not paste round
numbers from memory into the HF card.

## Upload (Hugging Face CLI)

From the repo root, after the ONNX exists:

```bash
# one-time
huggingface-cli login

# create a private or public model repo, then:
hf upload YOUR_ORG/coast-avnet-residual lab/models/weights/avnet_residual.onnx avnet_residual.onnx
```

Also upload this note (or a short model card that links back here):

```bash
hf upload YOUR_ORG/coast-avnet-residual lab/models/weights/README_HF.md README.md
```

Optional companion files (only if present and you want reproducibility):

- `lab/models/weights/avnet_v2_norm.npz` (input normalisation)
- a short pointer to `lab/models/run_residual_speed.py` for train/export

## Suggested model-card blurb (edit paths, not numbers)

```text
COAST residual speed ONNX (7-channel).
Input: (T, 7) = accel xyz, gyro xyz, v_prev. Output: speed residual Δ̂.
See lab/models/results/residual_speed/summary.md for measured leave-file-out
numbers. Absolute 6-channel AVNet is a separate artifact and loses to
persistence on this corpus.
```

This directory may not contain `avnet_residual.onnx` until export succeeds.
Absence of the file is not a pass.
