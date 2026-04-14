#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script for a fresh Ubuntu machine:
# 1) install system packages
# 2) create virtual environment
# 3) install Python dependencies from both project variants

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
CPU_ONLY=1

usage() {
  cat <<'EOF'
Usage:
  ./scripts/setup_ubuntu_fl.sh [--venv PATH] [--cpu-only] [--allow-gpu]

Options:
  --venv PATH   Set custom virtualenv path (default: .venv in repo root)
  --cpu-only    Install CPU-only PyTorch wheels (default)
  --allow-gpu   Allow default PyPI resolution (may pull large NVIDIA CUDA wheels)

This script is intended for Ubuntu with sudo access.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      if [[ -z "${2:-}" ]]; then
        echo "Error: missing value for --venv"
        exit 1
      fi
      VENV_DIR="$2"
      shift 2
      ;;
    --cpu-only)
      CPU_ONLY=1
      shift
      ;;
    --allow-gpu)
      CPU_ONLY=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${REPO_ROOT}/pyproject.toml" || ! -f "${REPO_ROOT}/baseline/pyproject.toml" ]]; then
  echo "Error: could not find expected pyproject files."
  echo "Run this script from inside the fl-resource-aware repository."
  exit 1
fi

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "Warning: detected '${ID:-unknown}' instead of Ubuntu. Continuing anyway."
  fi
fi

echo "[1/5] Installing system packages (requires sudo)..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  ca-certificates \
  curl

echo "[2/5] Creating virtual environment at: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "[3/5] Upgrading pip tooling..."
python -m pip install --upgrade pip setuptools wheel tomli
python -m pip cache purge >/dev/null 2>&1 || true

echo "[4/5] Installing project dependencies from both pyproject.toml files..."
if [[ "${CPU_ONLY}" == "1" ]]; then
  echo "Using CPU-only PyTorch install path to reduce download size and disk usage."
else
  echo "Using default dependency resolution (GPU-enabled wheels may be downloaded)."
fi
cd "${REPO_ROOT}"
FL_SETUP_CPU_ONLY="${CPU_ONLY}" \
python - <<'PY'
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

try:
    import tomllib  # py311+
except ModuleNotFoundError:  # py310
    import tomli as tomllib

repo_root = Path.cwd()
pyprojects = [repo_root / "pyproject.toml", repo_root / "baseline" / "pyproject.toml"]

deps: list[str] = []
seen: set[str] = set()

for p in pyprojects:
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    for dep in data.get("project", {}).get("dependencies", []):
        # Compatibility: some older configs used the wrong package name "dotenv".
        # The maintained package on PyPI is "python-dotenv".
        if dep.startswith("dotenv"):
            dep = dep.replace("dotenv", "python-dotenv", 1)
        if dep not in seen:
            seen.add(dep)
            deps.append(dep)

if not deps:
    raise SystemExit("No dependencies found in pyproject.toml files")

print("Dependencies to install:")
for dep in deps:
    print(f"  - {dep}")

cpu_only = os.environ.get("FL_SETUP_CPU_ONLY", "1") == "1"
machine = platform.machine().lower()

torch_deps: list[str] = []
other_deps: list[str] = []
for dep in deps:
  if dep.startswith("torch") or dep.startswith("torchvision"):
    torch_deps.append(dep)
  else:
    other_deps.append(dep)

pip_base = ["python", "-m", "pip", "install", "--no-cache-dir"]

if other_deps:
  subprocess.run([*pip_base, *other_deps], check=True)

if torch_deps:
  if cpu_only:
    cpu_index = "https://download.pytorch.org/whl/cpu"
    print(f"Installing torch packages from CPU index on {machine}: {cpu_index}")
    cpu_cmd = [*pip_base, "--index-url", cpu_index, *torch_deps]
    first_try = subprocess.run(cpu_cmd)
    if first_try.returncode != 0:
      print("CPU index install failed; falling back to default index.")
      subprocess.run([*pip_base, *torch_deps], check=True)
  else:
    subprocess.run([*pip_base, *torch_deps], check=True)
PY

echo "[5/5] Verifying tools..."
python --version
pip --version
if command -v flwr >/dev/null 2>&1; then
  flwr --version || true
else
  echo "Warning: 'flwr' command not found in PATH after installation."
fi

echo
echo "Setup complete. Activate with:"
echo "  source ${VENV_DIR}/bin/activate"
