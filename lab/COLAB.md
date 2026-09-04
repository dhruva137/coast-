# Optional: Google Colab maximize (only if you lack a local GPU)

Your machine already has an **RTX 5050** — use that first:

```bash
python lab/run_maximize_software.py
```

## Colab (backup)

1. Open [Google Colab](https://colab.research.google.com/) → Runtime → GPU.
2. New notebook, paste:

```python
!pip -q install torch numpy scipy matplotlib pandas onnx
!git clone --depth 1 https://github.com/dhruva137/SIH-2026.git
%cd SIH-2026
# Mount Drive and copy a pre-pulled IO-VNBD tree into data/raw/IO-VNBD
# or train with synthetic fallback:
!python lab/models/train_avnet.py --device auto --source auto --epochs 40 --n-windows 16384
!python lab/eval/iovnbd_plots.py
!python lab/eval/proposal_figures.py
```

3. Download `lab/models/weights/` and `lab/eval/figures/` back into the repo.

**Note:** IO-VNBD needs Git LFS (>1 MB CSVs). Without it, training falls back to synthetic windows — fine for plumbing, not for the PS proposal plots claim.
