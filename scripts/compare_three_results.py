#!/usr/bin/env python3
"""Compatibility wrapper for scripts/compare_final_results.py.

Legacy args from compare_three_results.py are translated to the final report
arguments. The final report requires a baseline results path.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def _build_new_argv() -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--final-results", default="")
    parser.add_argument("--final", default="")
    parser.add_argument("--baseline", default="")
    parser.add_argument("--original", default="")
    parser.add_argument("--tuned", default="")
    parser.add_argument("--report-json", default="")
    parser.add_argument("--plot-dir", default="")
    parser.add_argument("--label-final", default="")
    parser.add_argument("--label-baseline", default="")
    parser.add_argument("--label-original", default="")
    parser.add_argument("--label-tuned", default="")
    parser.add_argument("--config-final", default="")
    parser.add_argument("--config-baseline", default="")
    parser.add_argument("--config-original", default="")
    parser.add_argument("--config-tuned", default="")

    args, _unknown = parser.parse_known_args(sys.argv[1:])

    final_results = args.final_results or args.final or args.original or args.tuned
    if not final_results:
        raise SystemExit(
            "compare_three_results compatibility mode requires one of: "
            "--final-results, --final, --original, or --tuned"
        )
    if not args.baseline:
        raise SystemExit(
            "compare_three_results compatibility mode now requires --baseline "
            "for final report generation"
        )

    final_label = args.label_final or args.label_original or args.label_tuned or "final_strategy"
    baseline_label = args.label_baseline or "baseline_reference"

    final_config = args.config_final or args.config_original or args.config_tuned

    new_argv = [
        str(Path(__file__).with_name("compare_final_results.py")),
        "--final-results",
        final_results,
        "--baseline",
        args.baseline,
        "--label-final",
        final_label,
        "--label-baseline",
        baseline_label,
    ]

    if args.report_json:
        new_argv.extend(["--report-json", args.report_json])
    if args.plot_dir:
        new_argv.extend(["--plot-dir", args.plot_dir])
    if final_config:
        new_argv.extend(["--config-final", final_config])
    if args.config_baseline:
        new_argv.extend(["--config-baseline", args.config_baseline])

    return new_argv


def main() -> None:
    sys.argv = _build_new_argv()
    target = Path(__file__).with_name("compare_final_results.py")
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
