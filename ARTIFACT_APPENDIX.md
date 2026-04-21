# Artifact Appendix

This document describes how to access, run, and reproduce the artifact for this project.

## Description

### How to access

Primary access method (public source artifact):

```bash
git clone https://github.com/mirzuKHAN/fl-resource-aware.git
cd fl-resource-aware
```

Other access modes in the generic template (public package download, private package download, private machine access) are not required for this artifact.

Approximate disk space after setup and one complete report run: 6-12 GB (CPU-only path).

### Hardware dependencies

- CPU-only workflow supported.
- Recommended VM profile for smooth execution: 2-4 vCPU, 8-16 GB RAM.
- No specialized hardware counters or accelerators are required.

### Software dependencies

- Ubuntu 22.04+ (recommended).
- Python 3.10+.
- Main Python dependencies are declared in `pyproject.toml` and `baseline/pyproject.toml`, including:
  - `flwr[simulation]>=1.28.0`
  - `flwr-datasets[vision]>=0.6.0`
  - `torch>=2.8.0`
  - `torchvision>=0.23.0`
  - `matplotlib>=3.8.0`
  - `wandb==0.17.8`
  - `python-dotenv>=1.0.1`

### Data sets

- Dataset: Fashion-MNIST (`zalando-datasets/fashion_mnist`).
- Download behavior: automatic on first run through `flwr-datasets`.
- Approximate dataset/cache size: usually under 200 MB.

### Models

- Model: lightweight CNN implemented locally in `pytorch_example/task.py`.
- No external pretrained checkpoints are required.

## Installation

Recommended setup:

```bash
chmod +x scripts/setup_ubuntu_fl.sh scripts/run_and_report_final.sh
./scripts/setup_ubuntu_fl.sh --cpu-only
```

The setup script creates `.venv`, installs dependencies from both project variants, and verifies Python/pip/Flower tool availability.

## Experiment workflow

Run end-to-end final-vs-baseline experiment and generate report artifacts:

```bash
source .venv/bin/activate
./scripts/run_and_report_final.sh --rounds 10 --name artifact_eval
```

This produces a folder under `comparison_runs/` containing:
- `final_strategy_results.json`
- `baseline_reference_results.json`
- `final_strategy_vs_baseline_report.md`
- `final_strategy_vs_baseline_report.json`
- `final_vs_baseline_accuracy.png`
- `final_vs_baseline_loss.png`

## Evaluation and expected result

Expected qualitative outcome:
- Final strategy should generally outperform baseline on best accuracy and final loss.

Expected quantitative behavior (guideline, not exact bitwise target):
- Best accuracy delta (`final_strategy - baseline_reference`) is usually positive.
- On 10-round runs, a practical acceptable variation band is approximately +/-0.08 absolute for best accuracy due to stochastic effects.
- A representative successful run in this repository history reached final strategy best accuracy around 0.77 and baseline around 0.72; exact values vary by environment and randomness.

For quick verification, check the generated markdown report and confirm:
- "Best accuracy winner" is `final_strategy` in typical successful reproductions.
- Per-round deltas are mostly positive.

## Experiment customization

Useful knobs:
- `scripts/setup_ubuntu_fl.sh`
  - `--cpu-only` or `--allow-gpu`
  - `--venv PATH`
- `scripts/run_and_report_final.sh`
  - `--rounds N`
  - `--venv PATH`
  - `--name LABEL`
- Flower config in `pyproject.toml`
  - `resource-score-alpha`
  - `resource-score-beta`
  - `resource-score-gamma`
  - `fraction-train`, `fraction-evaluate`, `num-server-rounds`

## Reusability

Current workflow is script-based and does not yet expose an MLCommons CM interface.
The structure is modular enough to integrate CM in future work by wrapping setup and run steps as CM scripts.

## Notes

- The run automation sets `WANDB_MODE=disabled` during experiment runs to avoid external logging dependencies in artifact evaluation.
- For fair comparisons, keep VM type and round count fixed across repeated runs.

----

Prepared for artifact evaluation and reproducibility support for this project.
