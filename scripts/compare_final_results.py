#!/usr/bin/env python3
"""Generate the final strategy vs baseline report and plots.

Expected input files are JSON arrays (e.g. outputs/.../results.json) where each
item contains fields like:
- round
- evaluate_metrics_serverapp: {accuracy, loss}
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class VariantStats:
    name: str
    rounds: int
    final_accuracy: float | None
    best_accuracy: float | None
    best_accuracy_round: int | None
    mean_accuracy: float | None
    final_loss: float | None


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}, got {type(data).__name__}")
    return [x for x in data if isinstance(x, dict)]


def _load_optional_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _config_path(results_path: Path, config_arg: str) -> Path | None:
    if config_arg:
        return Path(config_arg).expanduser().resolve()
    sibling = results_path.parent / "run_config.json"
    if sibling.exists():
        return sibling
    return None


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def _fmt_config_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _metric(entry: dict[str, Any], section: str, key: str) -> float | None:
    sec = entry.get(section)
    if not isinstance(sec, dict):
        return None
    val = sec.get(key)
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _round(entry: dict[str, Any]) -> int | None:
    val = entry.get("round")
    if isinstance(val, int):
        return val
    return None


def _fmt(v: float | int | None, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{digits}f}"


def _fmt_with_round(value: float | None, round_no: int | None) -> str:
    if value is None:
        return "n/a"
    if round_no is None:
        return _fmt(value)
    return f"{_fmt(value)} (r{round_no})"


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def summarize(name: str, rows: list[dict[str, Any]]) -> VariantStats:
    server_rows: list[tuple[int, float | None, float | None]] = []
    for row in rows:
        r = _round(row)
        if r is None:
            continue
        acc = _metric(row, "evaluate_metrics_serverapp", "accuracy")
        loss = _metric(row, "evaluate_metrics_serverapp", "loss")
        server_rows.append((r, acc, loss))

    server_rows.sort(key=lambda x: x[0])

    final_accuracy = server_rows[-1][1] if server_rows else None
    final_loss = server_rows[-1][2] if server_rows else None

    acc_rows = [(r, a) for r, a, _ in server_rows if a is not None]
    best_accuracy = max((a for _, a in acc_rows), default=None)
    best_accuracy_round = next((r for r, a in acc_rows if a == best_accuracy), None)

    mean_accuracy = None
    if acc_rows:
        mean_accuracy = sum(a for _, a in acc_rows) / len(acc_rows)

    return VariantStats(
        name=name,
        rounds=len(server_rows),
        final_accuracy=final_accuracy,
        best_accuracy=best_accuracy,
        best_accuracy_round=best_accuracy_round,
        mean_accuracy=mean_accuracy,
        final_loss=final_loss,
    )


def _round_map(rows: list[dict[str, Any]]) -> dict[int, dict[str, float | None]]:
    out: dict[int, dict[str, float | None]] = {}
    for row in rows:
        r = _round(row)
        if r is None:
            continue
        out[r] = {
            "accuracy": _metric(row, "evaluate_metrics_serverapp", "accuracy"),
            "loss": _metric(row, "evaluate_metrics_serverapp", "loss"),
        }
    return out


def _series_for_metric(
    round_map: dict[int, dict[str, float | None]],
    metric: str,
) -> tuple[list[int], list[float]]:
    xs: list[int] = []
    ys: list[float] = []
    for r in sorted(round_map):
        val = round_map[r].get(metric)
        if val is None:
            continue
        xs.append(r)
        ys.append(val)
    return xs, ys


def _plot_metric(
    final_map: dict[int, dict[str, float | None]],
    baseline_map: dict[int, dict[str, float | None]],
    final_label: str,
    baseline_label: str,
    metric: str,
    ylabel: str,
    title: str,
    out_path: Path,
) -> None:
    fx, fy = _series_for_metric(final_map, metric)
    bx, by = _series_for_metric(baseline_map, metric)

    fig = plt.figure(figsize=(9.0, 5.0))
    ax = fig.add_subplot(1, 1, 1)

    if fx and fy:
        ax.plot(fx, fy, marker="o", linewidth=2, label=final_label)
    if bx and by:
        ax.plot(bx, by, marker="s", linewidth=2, label=baseline_label)

    ax.set_title(title)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def build_report(
    final_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    final_config: dict[str, Any],
    baseline_config: dict[str, Any],
    generated_at: str,
    final_label: str,
    baseline_label: str,
    plot_dir: Path | None,
) -> tuple[str, dict[str, Any]]:
    final = summarize(final_label, final_rows)
    baseline = summarize(baseline_label, baseline_rows)

    final_map = _round_map(final_rows)
    baseline_map = _round_map(baseline_rows)
    common_rounds = sorted(set(final_map).intersection(baseline_map))

    ranking_candidates = [final, baseline]
    ranking = sorted(
        ranking_candidates,
        key=lambda s: (float("-inf") if s.best_accuracy is None else s.best_accuracy),
        reverse=True,
    )
    overall_winner = ranking[0].name if ranking and ranking[0].best_accuracy is not None else "n/a"

    plot_paths: dict[str, str] = {}
    if plot_dir is not None:
        plot_dir.mkdir(parents=True, exist_ok=True)
        accuracy_plot = plot_dir / "final_vs_baseline_accuracy.png"
        loss_plot = plot_dir / "final_vs_baseline_loss.png"
        _plot_metric(
            final_map,
            baseline_map,
            final_label=final_label,
            baseline_label=baseline_label,
            metric="accuracy",
            ylabel="Accuracy",
            title="Final Strategy vs Baseline Accuracy by Round",
            out_path=accuracy_plot,
        )
        _plot_metric(
            final_map,
            baseline_map,
            final_label=final_label,
            baseline_label=baseline_label,
            metric="loss",
            ylabel="Loss",
            title="Final Strategy vs Baseline Loss by Round",
            out_path=loss_plot,
        )
        plot_paths["accuracy"] = accuracy_plot.name
        plot_paths["loss"] = loss_plot.name

    lines: list[str] = []
    lines.append("# Final Strategy Report (Final vs Baseline)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Generated at: {generated_at}")
    lines.append(f"- Report tag: final_strategy_vs_baseline")
    lines.append(f"- Compared variants: {final_label} vs {baseline_label}")
    lines.append(f"- Rounds observed ({final_label}): {final.rounds}")
    lines.append(f"- Rounds observed ({baseline_label}): {baseline.rounds}")

    lines.append("")
    lines.append("## Parameter Config")
    config_keys = sorted(set(final_config).union(baseline_config))
    if not config_keys:
        lines.append("- No run_config values found")
    else:
        lines.append(f"| Parameter | {final_label} | {baseline_label} |")
        lines.append("|---|---|---|")
        for key in config_keys:
            f_val = _md_escape(_fmt_config_value(final_config.get(key)))
            b_val = _md_escape(_fmt_config_value(baseline_config.get(key)))
            lines.append(f"| {key} | {f_val} | {b_val} |")

    lines.append("")
    lines.append("## Primary Metric (Best Accuracy)")
    lines.append(
        f"| Metric | {final_label} | {baseline_label} | Delta ({final_label} - {baseline_label}) |"
    )
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Best accuracy | {_fmt_with_round(final.best_accuracy, final.best_accuracy_round)} | {_fmt_with_round(baseline.best_accuracy, baseline.best_accuracy_round)} | {_fmt(_delta(final.best_accuracy, baseline.best_accuracy))} |"
    )

    lines.append("")
    lines.append("## Winners")
    lines.append(f"- Best accuracy winner: {overall_winner}")
    for idx, s in enumerate(ranking, start=1):
        lines.append(
            f"- Rank {idx}: {s.name} ({_fmt_with_round(s.best_accuracy, s.best_accuracy_round)})"
        )

    lines.append("")
    lines.append("## Per-round Accuracy")
    all_rounds = sorted(set(final_map).union(baseline_map))
    if not all_rounds:
        lines.append("- No rounds found")
    else:
        lines.append(f"| Round | {final_label} Accuracy | {baseline_label} Accuracy |")
        lines.append("|---:|---:|---:|")
        for r in all_rounds:
            lines.append(
                "| "
                f"{r} | {_fmt(final_map.get(r, {}).get('accuracy'))} | {_fmt(baseline_map.get(r, {}).get('accuracy'))} |"
            )

    lines.append("")
    lines.append(f"## Per-round Accuracy Deltas ({final_label} - {baseline_label})")
    if not common_rounds:
        lines.append("- No common rounds to compare")
    else:
        lines.append("| Round | Delta |")
        lines.append("|---:|---:|")
        for r in common_rounds:
            fb_delta = _delta(final_map[r]["accuracy"], baseline_map[r]["accuracy"])
            lines.append(f"| {r} | {_fmt(fb_delta)} |")

    if plot_paths:
        lines.append("")
        lines.append("## Plots")
        lines.append("### Accuracy")
        lines.append(f"![Final vs baseline accuracy]({plot_paths['accuracy']})")
        lines.append("")
        lines.append("### Loss")
        lines.append(f"![Final vs baseline loss]({plot_paths['loss']})")

    report = {
        "report_name": "final_strategy_vs_baseline_report",
        "report_tag": "final_strategy_vs_baseline",
        "generated_at": generated_at,
        "comparison_mode": "final_vs_baseline",
        "primary_metric": "best_accuracy",
        "labels": {
            "final_strategy": final_label,
            "baseline": baseline_label,
        },
        "parameter_config": {
            final_label: final_config,
            baseline_label: baseline_config,
        },
        "variants": {
            final_label: final.__dict__,
            baseline_label: baseline.__dict__,
        },
        "common_rounds": common_rounds,
        "ranking": [
            {
                "rank": i + 1,
                "name": s.name,
                "best_accuracy": s.best_accuracy,
                "best_accuracy_round": s.best_accuracy_round,
            }
            for i, s in enumerate(ranking)
        ],
        "winner": {
            "overall": overall_winner,
            "metric": "best_accuracy",
        },
        "delta_best_accuracy": {
            f"{final_label}_minus_{baseline_label}": _delta(final.best_accuracy, baseline.best_accuracy),
        },
        "plots": plot_paths,
    }
    return "\n".join(lines), report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare final strategy run results vs baseline and generate final report",
    )
    parser.add_argument(
        "--final-results",
        default="",
        help="Path to final strategy results.json",
    )
    parser.add_argument(
        "--final",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--improved-version",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--ours",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline results.json",
    )
    parser.add_argument(
        "--label-final",
        default="final_strategy",
        help="Display label for final strategy variant",
    )
    parser.add_argument(
        "--label-baseline",
        default="baseline_reference",
        help="Display label for baseline variant",
    )
    parser.add_argument(
        "--plot-dir",
        default="",
        help="Optional directory to save PNG plots",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Optional path to save machine-readable JSON report",
    )
    parser.add_argument(
        "--config-final",
        default="",
        help="Optional path to final strategy run_config.json",
    )
    parser.add_argument(
        "--config-baseline",
        default="",
        help="Optional path to baseline run_config.json",
    )

    args = parser.parse_args()

    final_path_input = args.final_results or args.final or args.improved_version or args.ours
    if not final_path_input:
        parser.error("missing required argument: --final-results")

    final_results_path = Path(final_path_input).expanduser().resolve()
    baseline_results_path = Path(args.baseline).expanduser().resolve()

    final_rows = _load_json(final_results_path)
    baseline_rows = _load_json(baseline_results_path)

    final_config = _load_optional_json_object(
        _config_path(final_results_path, args.config_final)
    )
    baseline_config = _load_optional_json_object(
        _config_path(baseline_results_path, args.config_baseline)
    )

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    plot_dir = Path(args.plot_dir).expanduser().resolve() if args.plot_dir else None

    report_md, report_obj = build_report(
        final_rows=final_rows,
        baseline_rows=baseline_rows,
        final_config=final_config,
        baseline_config=baseline_config,
        generated_at=generated_at,
        final_label=args.label_final,
        baseline_label=args.label_baseline,
        plot_dir=plot_dir,
    )
    print(report_md)

    if args.report_json:
        out_path = Path(args.report_json).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(report_obj, f, indent=2)


if __name__ == "__main__":
    main()
