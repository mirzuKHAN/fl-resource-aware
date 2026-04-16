# Final Strategy Report (Final vs Baseline)

## Summary
- Generated at: 2026-04-17T07:24:00+08:00
- Report tag: final_strategy_vs_baseline
- Compared variants: final_strategy vs baseline_reference
- Rounds observed (final_strategy): 10
- Rounds observed (baseline_reference): 10

## Parameter Config
| Parameter | final_strategy | baseline_reference |
|---|---|---|
| fraction-evaluate | 0.5 | 0.5 |
| fraction-train | 0.25 | 0.25 |
| local-epochs | 1 | 1 |
| num-server-rounds | 10 | 10 |
| resource-score-alpha | 0.4 | n/a |
| resource-score-beta | 0.4 | n/a |
| resource-score-gamma | 0.2 | n/a |
| server-device | cpu | cpu |

## Primary Metric (Best Accuracy)
| Metric | final_strategy | baseline_reference | Delta (final_strategy - baseline_reference) |
|---|---:|---:|---:|
| Best accuracy | 0.7296 (r9) | 0.1000 (r1) | 0.6296 |

## Winners
- Best accuracy winner: final_strategy
- Rank 1: final_strategy (0.7296 (r9))
- Rank 2: baseline_reference (0.1000 (r1))

## Per-round Accuracy
| Round | final_strategy Accuracy | baseline_reference Accuracy |
|---:|---:|---:|
| 1 | 0.4044 | 0.1000 |
| 2 | 0.5858 | 0.1000 |
| 3 | 0.6350 | 0.1000 |
| 4 | 0.6753 | 0.1000 |
| 5 | 0.6666 | 0.1000 |
| 6 | 0.6971 | 0.1000 |
| 7 | 0.7024 | 0.1000 |
| 8 | 0.7284 | 0.1000 |
| 9 | 0.7296 | 0.1000 |
| 10 | 0.7134 | 0.1000 |

## Per-round Accuracy Deltas (final_strategy - baseline_reference)
| Round | Delta |
|---:|---:|
| 1 | 0.3044 |
| 2 | 0.4858 |
| 3 | 0.5350 |
| 4 | 0.5753 |
| 5 | 0.5666 |
| 6 | 0.5971 |
| 7 | 0.6024 |
| 8 | 0.6284 |
| 9 | 0.6296 |
| 10 | 0.6134 |

## Plots
### Accuracy
![Final vs baseline accuracy](final_vs_baseline_accuracy.png)

### Loss
![Final vs baseline loss](final_vs_baseline_loss.png)
