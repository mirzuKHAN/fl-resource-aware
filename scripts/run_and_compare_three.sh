#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[compat] scripts/run_and_compare_three.sh -> scripts/run_and_report_final.sh"
echo "[compat] tuned_parameter is archived at archive/tuned_parameter and is not used for final reports."
exec "${SCRIPT_DIR}/run_and_report_final.sh" "$@"
