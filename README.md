---
tags: [advanced, vision, fds, wandb]
dataset: [Fashion-MNIST]
framework: [torch, torchvision]
---

# Resource-Aware Client Selection for Efficient Federated Learning

This repository contains the implementation of a **Resource-Aware Client Selection Strategy** for Federated Learning (FL) in heterogeneous cloud-edge environments. This project is built using the [Flower](https://flower.ai/) framework and PyTorch.

### Group Members
- **Mirza Shaimardanov** (Student ID: 57563329)
- **DAULETALENA Dina** (Student ID: 57272366)
- **Chen Pang Fai** (Student ID: 57840595)

---

## 📌 Project Overview
Federated Learning allows collaborative model training across decentralized edge devices (e.g., smartphones, IoT sensors) without sharing raw data, ensuring privacy. However, real-world edge environments suffer from **device heterogeneity**—differences in computing power, battery life, and network bandwidth. Standard algorithms like FedAvg rely on random client selection, which can lead to slow convergence, dropped connections, and communication bottlenecks.

This research project replaces standard random selection with a novel **Multi-Factor "Resource-Score" Algorithm**.

## 🧠 The Resource-Aware Selection Strategy
Instead of picking clients at random, the server assigns a score to available clients based on their simulated resource constraints. The score is calculated using the following formula:

$$Score = (\alpha \times \text{BatteryLevel}) + (\beta \times \text{NetworkBandwidth}) - (\gamma \times \text{PastFailures})$$

- **Battery Level:** Prioritizes devices with higher remaining charge.
- **Network Bandwidth:** Prioritizes devices with faster, more stable connections.
- **Past Failures:** Penalizes "straggler" nodes that frequently drop out.

By selecting the top-scoring clients, the strategy mitigates the impact of stragglers, reduces communication overhead, and maintains a stable training loss.

---

## 📂 Repository Structure
This project follows the standard Flower framework app structure:

```text
├── pyproject.toml              # Original improved_version app metadata
├── README.md                   # Project documentation
├── pytorch_example/            # Final strategy code (active)
├── archive/
│   └── tuned_parameter/        # Archived tuned-parameter app (historical)
├── baseline/                   # Baseline app
└── scripts/                    # Setup and comparison automation
    ├── __init__.py
    ├── client_app.py           # Client-side training and evaluation logic
    ├── server_app.py           # Server-side setup and hyperparameter configuration
    ├── strategy.py             # CustomFedAvg strategy with Resource-Aware Selection
    └── task.py                 # PyTorch model definition and dataset loading
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10 or newer
- [Flower (flwr)](https://flower.ai/docs/framework/)
- PyTorch

### Installation
Clone the repository and install the dependencies in a virtual environment:

```bash
git clone https://github.com/mirzuKHAN/fl-resource-aware.git
cd fl-resource-aware

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install the project and dependencies
pip install -e .
```

### One-command setup for fresh Ubuntu

For a new Ubuntu machine, use the follwing command:

```bash
cd fl-resource-aware
sudo chmod +x -R scripts/
sudo ./scripts/setup_ubuntu_fl.sh
```

This script will:
- Install required system packages (`python3`, `python3-venv`, `python3-pip`, compiler tools)
- Create a virtual environment at `.venv`
- Install all Python dependencies from both `pyproject.toml` files (main + baseline)

### Automated final report run (final strategy vs baseline)

After setup, run:

```bash
source .venv/bin/activate
sudo ./scripts/run_and_report_final.sh --rounds 10
```

This automation script will:
- Run Flower simulation for final strategy (`./`)
- Run Flower simulation for baseline (`./baseline/`)
- Find the newest `results.json` from each run
- Call `scripts/compare_final_results.py`
- Generate final report artifacts under `comparison_runs/<timestamp>_final_strategy_vs_baseline/`

Generated artifact names:
- `final_strategy_vs_baseline_report.md`
- `final_strategy_vs_baseline_report.json`
- `final_vs_baseline_accuracy.png`
- `final_vs_baseline_loss.png`

Compatibility notes:
- `scripts/run_and_compare.sh` now forwards to `scripts/run_and_report_final.sh`.
- `scripts/run_and_compare_three.sh` now forwards to `scripts/run_and_report_final.sh`.
- `scripts/compare_results.py` now forwards to `scripts/compare_final_results.py`.
- Archived tuned app is stored at `archive/tuned_parameter/` and is not used in final report generation.

---

## 🏃 Running the Simulation

You can run the full single-node heterogeneous simulation using the Flower CLI. The simulation will spawn multiple client processes with artificially injected resource metrics.

Run the following command from the root of the repository:

```bash
flwr run . --stream
```

### What happens during the run?
1. The server initializes a global PyTorch model (Fashion-MNIST).
2. For each round (10 rounds default), the server queries connected clients for their metrics.
3. The custom `strategy.py` calculates the resource score for each node and selects the top 12 most capable devices.
4. Selected devices perform local training (`client_app.py`).
5. The server aggregates the weights, logs the validation accuracy, and drops the learning rate midway through training to ensure convergence.

---

## 📊 Evaluation & Results
Our evaluation demonstrates that the Resource-Aware selection prevents model divergence often seen with random client dropout. In testing on the Fashion-MNIST dataset in a non-IID setting:
- The custom learning rate schedule and top-K node selection stabilized gradients.
- Global accuracy climbed consistently across rounds, reaching over **66%** by Round 8 without training loss explosion.
- The model actively ignored nodes with sub-10% battery or single-digit bandwidth speeds, proving the viability of the selection formula.

---

## 🧪 Artifact Appendix (Reproducibility)

A complete project-wide artifact description and reproducibility guide is available in:

- [ARTIFACT_APPENDIX.md](ARTIFACT_APPENDIX.md)

This appendix includes:
- Hardware/software requirements
- Dataset/model details
- Step-by-step installation and experiment workflow
- Expected result ranges and allowable variation
- Customization knobs for further experiments

### Quick Reproduction Commands

```bash
chmod +x scripts/setup_ubuntu_fl.sh scripts/run_and_report_final.sh
./scripts/setup_ubuntu_fl.sh --cpu-only
source .venv/bin/activate
./scripts/run_and_report_final.sh --rounds 10 --name artifact_eval
```

Expected generated report location pattern:

- `comparison_runs/<timestamp>_artifact_eval/final_strategy_vs_baseline_report.md`

