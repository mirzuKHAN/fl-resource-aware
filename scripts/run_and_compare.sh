#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[compat] scripts/run_and_compare.sh -> scripts/run_and_report_final.sh"
exec "${SCRIPT_DIR}/run_and_report_final.sh" "$@"
