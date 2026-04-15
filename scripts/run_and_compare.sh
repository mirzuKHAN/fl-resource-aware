#!/usr/bin/env bash
set -euo pipefail

# Run both variants (improved_version and baseline), then compare results.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
ROUNDS=5
RUN_NAME=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_and_compare.sh [--rounds N] [--venv PATH] [--name LABEL]

Options:
  --rounds N    Number of FL server rounds for both runs (default: 5)
  --venv PATH   Virtualenv path (default: .venv in repo root)
  --name LABEL  Optional tag for output folder name

Notes:
  - If the virtualenv or flwr command is missing, setup will run automatically.
  - Setup requires sudo because system packages are installed on first run.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rounds)
      ROUNDS="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --name)
      RUN_NAME="$2"
      shift 2
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

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Virtualenv not found at ${VENV_DIR}. Running setup script first..."
  "${REPO_ROOT}/scripts/setup_ubuntu_fl.sh" --venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if ! command -v flwr >/dev/null 2>&1; then
  echo "'flwr' not found. Re-running setup script to install dependencies..."
  "${REPO_ROOT}/scripts/setup_ubuntu_fl.sh" --venv "${VENV_DIR}"
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
fi

stamp="$(date +"%Y%m%d_%H%M%S")"
if [[ -n "${RUN_NAME}" ]]; then
  out_dir="${REPO_ROOT}/comparison_runs/${stamp}_${RUN_NAME}"
else
  out_dir="${REPO_ROOT}/comparison_runs/${stamp}"
fi
mkdir -p "${out_dir}"

latest_results_json_any() {
  find "${REPO_ROOT}" "${REPO_ROOT}/baseline" -type f -name "results.json" 2>/dev/null \
    | grep '/outputs/' \
    | sort \
    | tail -n 1
}

latest_results_json_since_marker() {
  local marker_file="$1"
  find "${REPO_ROOT}" "${REPO_ROOT}/baseline" -type f -name "results.json" -newer "${marker_file}" 2>/dev/null \
    | grep '/outputs/' \
    | sort \
    | tail -n 1
}

run_variant() {
  local variant_name="$1"
  local variant_dir="$2"
  local log_file="$3"

  echo
  echo "========== Running ${variant_name} =========="
  echo "Directory: ${variant_dir}"

  (
    cd "${variant_dir}"
    # Disable online wandb login requirement on fresh machines.
    export WANDB_MODE=disabled
    flwr run . --run-config "num-server-rounds=${ROUNDS}" --stream
  ) | tee "${log_file}"
}

improved_marker="${out_dir}/.improved_version.marker"
touch "${improved_marker}"
run_variant "improved_version" "${REPO_ROOT}" "${out_dir}/improved_version.log"
IMPROVED_RESULTS="$(latest_results_json_since_marker "${improved_marker}")"
if [[ -z "${IMPROVED_RESULTS}" ]]; then
  IMPROVED_RESULTS="$(latest_results_json_any)"
fi

baseline_marker="${out_dir}/.baseline.marker"
touch "${baseline_marker}"
run_variant "baseline" "${REPO_ROOT}/baseline" "${out_dir}/baseline.log"
BASELINE_RESULTS="$(latest_results_json_since_marker "${baseline_marker}")"
if [[ -z "${BASELINE_RESULTS}" ]]; then
  BASELINE_RESULTS="$(latest_results_json_any)"
fi

if [[ -z "${IMPROVED_RESULTS}" || -z "${BASELINE_RESULTS}" ]]; then
  echo "Error: could not find one or both results.json files."
  echo "Improved version: ${IMPROVED_RESULTS:-<missing>}"
  echo "Baseline: ${BASELINE_RESULTS:-<missing>}"
  exit 1
fi

cp "${IMPROVED_RESULTS}" "${out_dir}/improved_version_results.json"
cp "${BASELINE_RESULTS}" "${out_dir}/baseline_results.json"

REPORT_JSON="${out_dir}/comparison_report.json"
REPORT_MD="${out_dir}/comparison_report.md"

python "${REPO_ROOT}/scripts/compare_results.py" \
  --improved-version "${IMPROVED_RESULTS}" \
  --baseline "${BASELINE_RESULTS}" \
  --report-json "${REPORT_JSON}" | tee "${REPORT_MD}"

cat <<EOF

Done.
- Improved version results: ${IMPROVED_RESULTS}
- Baseline results: ${BASELINE_RESULTS}
- Copied improved version results: ${out_dir}/improved_version_results.json
- Copied baseline results: ${out_dir}/baseline_results.json
- Comparison Markdown report: ${REPORT_MD}
- Comparison JSON report: ${REPORT_JSON}
EOF
