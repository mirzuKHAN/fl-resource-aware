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
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # Project documentation
└── pytorch_example/            # Core application code
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
git clone https://github.com/mirzuKHAN/fed-learn-resource-aware.git
cd fed-learn-resource-aware

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install the project and dependencies
pip install -e .
```

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

