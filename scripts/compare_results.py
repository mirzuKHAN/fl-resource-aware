#!/usr/bin/env python3
"""Compare Flower run results between two experiment variants.

Expected input files are JSON arrays (e.g. outputs/.../results.json) where each item
contains fields like:
- round
- evaluate_metrics_serverapp: {accuracy, loss}
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class VariantStats:
    name: str
    rounds: int
    final_accuracy: float | None
    final_loss: float | None
    best_accuracy: float | None
    best_accuracy_round: int | None
    lowest_loss: float | None
    lowest_loss_round: int | None
    mean_accuracy: float | None


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}, got {type(data).__name__}")
    return [x for x in data if isinstance(x, dict)]


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
    rounds = len(server_rows)

    final_accuracy = server_rows[-1][1] if server_rows else None
    final_loss = server_rows[-1][2] if server_rows else None

    acc_rows = [(r, a) for r, a, _ in server_rows if a is not None]
    loss_rows = [(r, l) for r, _, l in server_rows if l is not None]

    best_accuracy = max((a for _, a in acc_rows), default=None)
    best_accuracy_round = next((r for r, a in acc_rows if a == best_accuracy), None)

    lowest_loss = min((l for _, l in loss_rows), default=None)
    lowest_loss_round = next((r for r, l in loss_rows if l == lowest_loss), None)

    mean_accuracy = None
    if acc_rows:
        mean_accuracy = sum(a for _, a in acc_rows) / len(acc_rows)

    return VariantStats(
        name=name,
        rounds=rounds,
        final_accuracy=final_accuracy,
        final_loss=final_loss,
        best_accuracy=best_accuracy,
        best_accuracy_round=best_accuracy_round,
        lowest_loss=lowest_loss,
        lowest_loss_round=lowest_loss_round,
        mean_accuracy=mean_accuracy,
    )


def _fmt(v: float | int | None, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{digits}f}"


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def _winner(
    improved_val: float | None,
    baseline_val: float | None,
    higher_is_better: bool,
    tol: float = 1e-12,
) -> str:
    if improved_val is None or baseline_val is None:
        return "n/a"
    if abs(improved_val - baseline_val) <= tol:
        return "tie"
    if higher_is_better:
        return "improved_version" if improved_val > baseline_val else "baseline"
    return "improved_version" if improved_val < baseline_val else "baseline"


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


def _fmt_with_round(value: float | None, round_no: int | None) -> str:
    if value is None:
        return "n/a"
    if round_no is None:
        return _fmt(value)
    return f"{_fmt(value)} (r{round_no})"


def build_report(
    improved_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    generated_at: str,
) -> tuple[str, dict[str, Any]]:
    improved = summarize("improved_version", improved_rows)
    base = summarize("baseline", baseline_rows)

    lines: list[str] = []
    lines.append("# Flower Results Comparison (Server Metrics)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Generated at: {generated_at}")
    lines.append(f"- Rounds observed (improved_version): {improved.rounds}")
    lines.append(f"- Rounds observed (baseline): {base.rounds}")
    lines.append("")
    lines.append("## Key Metrics")
    lines.append("| Metric | improved_version | baseline | Delta (improved_version - baseline) |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Final accuracy | {_fmt(improved.final_accuracy)} | {_fmt(base.final_accuracy)} | {_fmt(_delta(improved.final_accuracy, base.final_accuracy))} |"
    )
    lines.append(
        f"| Final loss | {_fmt(improved.final_loss)} | {_fmt(base.final_loss)} | {_fmt(_delta(improved.final_loss, base.final_loss))} |"
    )
    lines.append(
        f"| Best accuracy | {_fmt_with_round(improved.best_accuracy, improved.best_accuracy_round)} | {_fmt_with_round(base.best_accuracy, base.best_accuracy_round)} | {_fmt(_delta(improved.best_accuracy, base.best_accuracy))} |"
    )
    lines.append(
        f"| Lowest loss | {_fmt_with_round(improved.lowest_loss, improved.lowest_loss_round)} | {_fmt_with_round(base.lowest_loss, base.lowest_loss_round)} | {_fmt(_delta(improved.lowest_loss, base.lowest_loss))} |"
    )
    lines.append(
        f"| Mean accuracy | {_fmt(improved.mean_accuracy)} | {_fmt(base.mean_accuracy)} | {_fmt(_delta(improved.mean_accuracy, base.mean_accuracy))} |"
    )

    category_winners = {
        "final_accuracy": _winner(
            improved.final_accuracy, base.final_accuracy, higher_is_better=True
        ),
        "final_loss": _winner(improved.final_loss, base.final_loss, higher_is_better=False),
        "best_accuracy": _winner(
            improved.best_accuracy, base.best_accuracy, higher_is_better=True
        ),
        "lowest_loss": _winner(
            improved.lowest_loss, base.lowest_loss, higher_is_better=False
        ),
        "mean_accuracy": _winner(
            improved.mean_accuracy, base.mean_accuracy, higher_is_better=True
        ),
    }

    improved_points = sum(1 for w in category_winners.values() if w == "improved_version")
    baseline_points = sum(1 for w in category_winners.values() if w == "baseline")
    tie_points = sum(1 for w in category_winners.values() if w == "tie")
    na_points = sum(1 for w in category_winners.values() if w == "n/a")

    if improved_points > baseline_points:
        overall_winner = "improved_version"
    elif baseline_points > improved_points:
        overall_winner = "baseline"
    elif improved_points == baseline_points and improved_points > 0:
        overall_winner = "tie"
    else:
        overall_winner = "n/a"

    lines.append("")
    lines.append("## Winners")
    lines.append(f"- Final accuracy winner: {category_winners['final_accuracy']}")
    lines.append(f"- Final loss winner: {category_winners['final_loss']}")
    lines.append(f"- Best accuracy winner: {category_winners['best_accuracy']}")
    lines.append(f"- Lowest loss winner: {category_winners['lowest_loss']}")
    lines.append(f"- Mean accuracy winner: {category_winners['mean_accuracy']}")
    lines.append(
        f"- Total score: improved_version={improved_points} | baseline={baseline_points} | tie={tie_points} | n/a={na_points}"
    )
    lines.append(f"- Overall winner: {overall_winner}")

    improved_map = _round_map(improved_rows)
    base_map = _round_map(baseline_rows)
    common_rounds = sorted(set(improved_map).intersection(base_map))

    lines.append("")
    lines.append("## Per-round Deltas (improved_version - baseline)")
    if not common_rounds:
        lines.append("- No common rounds to compare")
    else:
        lines.append("| Round | Accuracy Delta | Loss Delta |")
        lines.append("|---:|---:|---:|")
        for r in common_rounds:
            acc_d = _delta(improved_map[r]["accuracy"], base_map[r]["accuracy"])
            loss_d = _delta(improved_map[r]["loss"], base_map[r]["loss"])
            lines.append(f"| {r} | {_fmt(acc_d)} | {_fmt(loss_d)} |")

    report = {
        "generated_at": generated_at,
        "improved_version": improved.__dict__,
        "baseline": base.__dict__,
        "common_rounds": common_rounds,
        "delta": {
            "final_accuracy": _delta(improved.final_accuracy, base.final_accuracy),
            "final_loss": _delta(improved.final_loss, base.final_loss),
            "mean_accuracy": _delta(improved.mean_accuracy, base.mean_accuracy),
        },
        "winner": {
            "by_category": category_winners,
            "score": {
                "improved_version": improved_points,
                "baseline": baseline_points,
                "tie": tie_points,
                "n/a": na_points,
            },
            "overall": overall_winner,
        },
    }
    return "\n".join(lines), report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare improved FL run results vs baseline run results",
    )
    parser.add_argument(
        "--improved-version",
        default="",
        help="Path to improved_version results.json",
    )
    # Backward compatibility for older scripts that pass --ours
    parser.add_argument("--ours", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--baseline", required=True, help="Path to baseline results.json"
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Optional path to save machine-readable JSON report",
    )
    args = parser.parse_args()

    improved_path_input = args.improved_version or args.ours
    if not improved_path_input:
        parser.error("missing required argument: --improved-version")

    improved_path = Path(improved_path_input).expanduser().resolve()
    baseline_path = Path(args.baseline).expanduser().resolve()

    improved_rows = _load_json(improved_path)
    baseline_rows = _load_json(baseline_path)

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    report_txt, report_obj = build_report(improved_rows, baseline_rows, generated_at)
    print(report_txt)

    if args.report_json:
        out_path = Path(args.report_json).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(report_obj, f, indent=2)


if __name__ == "__main__":
    main()
