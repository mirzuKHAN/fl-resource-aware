#!/usr/bin/env bash
set -euo pipefail

# Run final strategy (repo root) vs baseline, then generate final report.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
ROUNDS=10
RUN_NAME=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_and_report_final.sh [--rounds N] [--venv PATH] [--name LABEL]

Options:
  --rounds N    Number of FL server rounds for final and baseline runs (default: 10)
  --venv PATH   Virtualenv path (default: .venv in repo root)
  --name LABEL  Optional suffix for output folder name

Runs:
  1) final_strategy (repo root)
  2) baseline_reference (repo root/baseline)
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

if ! python -c "import matplotlib" >/dev/null 2>&1; then
  echo "'matplotlib' not found. Installing plotting dependency..."
  python -m pip install --no-cache-dir "matplotlib>=3.8.0"
fi

stamp="$(date +"%Y%m%d_%H%M%S")"
folder_tag="final_strategy_vs_baseline"
if [[ -n "${RUN_NAME}" ]]; then
  out_dir="${REPO_ROOT}/comparison_runs/${stamp}_${RUN_NAME}"
else
  out_dir="${REPO_ROOT}/comparison_runs/${stamp}_${folder_tag}"
fi
mkdir -p "${out_dir}"

latest_results_json_any() {
  find "${REPO_ROOT}" "${REPO_ROOT}/baseline" -type f -name "results.json" 2>/dev/null \
    | awk '/\/outputs\// { print }' \
    | sort \
    | tail -n 1
}

latest_results_json_since_marker() {
  local marker_file="$1"
  find "${REPO_ROOT}" "${REPO_ROOT}/baseline" -type f -name "results.json" -newer "${marker_file}" 2>/dev/null \
    | awk '/\/outputs\// { print }' \
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
    export WANDB_MODE=disabled
    flwr run . --run-config "num-server-rounds=${ROUNDS}" --stream
  ) | tee "${log_file}"
}

final_marker="${out_dir}/.final_strategy.marker"
touch "${final_marker}"
run_variant "final_strategy" "${REPO_ROOT}" "${out_dir}/final_strategy.log"
FINAL_RESULTS="$(latest_results_json_since_marker "${final_marker}")"
if [[ -z "${FINAL_RESULTS}" ]]; then
  FINAL_RESULTS="$(latest_results_json_any)"
fi

baseline_marker="${out_dir}/.baseline_reference.marker"
touch "${baseline_marker}"
run_variant "baseline_reference" "${REPO_ROOT}/baseline" "${out_dir}/baseline_reference.log"
BASELINE_RESULTS="$(latest_results_json_since_marker "${baseline_marker}")"
if [[ -z "${BASELINE_RESULTS}" ]]; then
  BASELINE_RESULTS="$(latest_results_json_any)"
fi

if [[ -z "${FINAL_RESULTS}" || -z "${BASELINE_RESULTS}" ]]; then
  echo "Error: could not find one or both results.json files."
  echo "Final strategy: ${FINAL_RESULTS:-<missing>}"
  echo "Baseline: ${BASELINE_RESULTS:-<missing>}"
  exit 1
fi

cp "${FINAL_RESULTS}" "${out_dir}/final_strategy_results.json"
cp "${BASELINE_RESULTS}" "${out_dir}/baseline_reference_results.json"

FINAL_CONFIG_PATH="$(dirname "${FINAL_RESULTS}")/run_config.json"
BASELINE_CONFIG_PATH="$(dirname "${BASELINE_RESULTS}")/run_config.json"

FINAL_CONFIG_DISPLAY="<missing>"
BASELINE_CONFIG_DISPLAY="<missing>"
FINAL_CONFIG_COPY_DISPLAY="<missing>"
BASELINE_CONFIG_COPY_DISPLAY="<missing>"

if [[ -f "${FINAL_CONFIG_PATH}" ]]; then
  FINAL_CONFIG_DISPLAY="${FINAL_CONFIG_PATH}"
  cp "${FINAL_CONFIG_PATH}" "${out_dir}/final_strategy_run_config.json"
  FINAL_CONFIG_COPY_DISPLAY="${out_dir}/final_strategy_run_config.json"
fi
if [[ -f "${BASELINE_CONFIG_PATH}" ]]; then
  BASELINE_CONFIG_DISPLAY="${BASELINE_CONFIG_PATH}"
  cp "${BASELINE_CONFIG_PATH}" "${out_dir}/baseline_reference_run_config.json"
  BASELINE_CONFIG_COPY_DISPLAY="${out_dir}/baseline_reference_run_config.json"
fi

REPORT_JSON="${out_dir}/final_strategy_vs_baseline_report.json"
REPORT_MD="${out_dir}/final_strategy_vs_baseline_report.md"
REPORT_PLOT_ACCURACY="${out_dir}/final_vs_baseline_accuracy.png"
REPORT_PLOT_LOSS="${out_dir}/final_vs_baseline_loss.png"

COMPARE_ARGS=(
  --final-results "${FINAL_RESULTS}"
  --baseline "${BASELINE_RESULTS}"
  --label-final "final_strategy"
  --label-baseline "baseline_reference"
  --plot-dir "${out_dir}"
  --report-json "${REPORT_JSON}"
)

if [[ -f "${FINAL_CONFIG_PATH}" ]]; then
  COMPARE_ARGS+=(--config-final "${FINAL_CONFIG_PATH}")
fi
if [[ -f "${BASELINE_CONFIG_PATH}" ]]; then
  COMPARE_ARGS+=(--config-baseline "${BASELINE_CONFIG_PATH}")
fi

python "${REPO_ROOT}/scripts/compare_final_results.py" "${COMPARE_ARGS[@]}" | tee "${REPORT_MD}"

cat <<EOF

Done.
- Report tag: ${folder_tag}
- Final strategy results: ${FINAL_RESULTS}
- Baseline results: ${BASELINE_RESULTS}
- Final run config: ${FINAL_CONFIG_DISPLAY}
- Baseline run config: ${BASELINE_CONFIG_DISPLAY}
- Copied final results: ${out_dir}/final_strategy_results.json
- Copied baseline results: ${out_dir}/baseline_reference_results.json
- Copied final run config: ${FINAL_CONFIG_COPY_DISPLAY}
- Copied baseline run config: ${BASELINE_CONFIG_COPY_DISPLAY}
- Final Markdown report: ${REPORT_MD}
- Final JSON report: ${REPORT_JSON}
- Accuracy plot: ${REPORT_PLOT_ACCURACY}
- Loss plot: ${REPORT_PLOT_LOSS}
EOF
