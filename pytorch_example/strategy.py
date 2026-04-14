"""pytorch-example: A Flower / PyTorch app."""

import io
import json
import os
import random
import time
from logging import INFO
from pathlib import Path
from typing import Callable, Iterable, Optional

import torch
import wandb
from flwr.app import (
    ArrayRecord,
    ConfigRecord,
    Message,
    MessageType,
    MetricRecord,
    RecordDict,
)
from flwr.common import log, logger
from flwr.serverapp import Grid
from flwr.serverapp.strategy import FedAvg, Result
from flwr.serverapp.strategy.strategy_utils import log_strategy_start_info

PROJECT_NAME = "FLOWER-advanced-pytorch"


class CustomFedAvg(FedAvg):
    """FedAvg extended with a Resource-Score client selection strategy.

    Instead of selecting clients randomly (standard FedAvg), this strategy scores
    every available node using a weighted formula:

        Score = (α × BatteryLevel) + (β × NetworkBandwidth) − (γ × PastFailures)

    The top-scoring nodes are selected for each training round.  Battery level
    (0–100) and network bandwidth (1–100 Mbps) are simulated deterministically
    from the node ID, while past failures are accumulated across rounds.

    This strategy also: (1) saves results to the filesystem each round,
    (2) saves a checkpoint of the global model when a new best is found,
    (3) logs results to W&B.

    Parameters
    ----------
    alpha : float (default: 0.4)
        Weight for the BatteryLevel term in the resource score.
    beta : float (default: 0.4)
        Weight for the NetworkBandwidth term in the resource score.
    gamma : float (default: 0.2)
        Penalty weight for the PastFailures term in the resource score.
    **kwargs
        All other keyword arguments are forwarded to :class:`FedAvg`.
    """

    def __init__(
        self,
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        # Maps node_id -> cumulative number of failed rounds
        self.past_failures: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Resource-score helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _simulate_battery(node_id: int) -> float:
        """Return a deterministic battery level in [0, 100] for *node_id*."""
        return random.Random(node_id ^ 0xABCDEF).uniform(0, 100)

    @staticmethod
    def _simulate_bandwidth(node_id: int) -> float:
        """Return a deterministic network bandwidth in [1, 100] Mbps for *node_id*."""
        return random.Random(node_id ^ 0x123456).uniform(1, 100)

    def _compute_resource_score(self, node_id: int) -> float:
        """Compute the resource score for *node_id* using the weighted formula."""
        battery = self._simulate_battery(node_id)
        bandwidth = self._simulate_bandwidth(node_id)
        failures = self.past_failures.get(node_id, 0)
        return (
            (self.alpha * battery)
            + (self.beta * bandwidth)
            - (self.gamma * failures)
        )

    def set_save_path_and_run_dir(self, path: Path, run_dir: str):
        """Set the path where results and model checkpoints will be saved."""
        self.save_path = path
        self.run_dir = run_dir

    def _update_best_acc(
        self, current_round: int, accuracy: float, arrays: ArrayRecord
    ) -> None:
        """Update best accuracy and save model checkpoint if current accuracy is
        higher."""
        if accuracy > self.best_acc_so_far:
            self.best_acc_so_far = accuracy
            logger.log(INFO, "💡 New best global model found: %f", accuracy)
            # Save the PyTorch model
            file_name = f"model_state_acc_{accuracy}_round_{current_round}.pth"
            torch.save(arrays.to_torch_state_dict(), self.save_path / file_name)
            logger.log(INFO, "💾 New best model saved to disk: %s", file_name)

    def save_metrics_as_json(self, current_round: int, result: Result) -> None:
        """Save the current results to a JSON file."""

        # Load current JSON if file exists
        if os.path.exists(f"{self.save_path}/results.json"):
            with open(f"{self.save_path}/results.json", "r", encoding="utf-8") as fp:
                try:
                    results = json.load(fp)
                except json.JSONDecodeError:
                    results = []
        else:
            results = []

        # Extract metrics from current round
        last_train_metrics = dict(result.train_metrics_clientapp.get(current_round, {}))
        last_eval_client_metrics = dict(
            result.evaluate_metrics_clientapp.get(current_round, {})
        )
        last_eval_server_metrics = dict(
            result.evaluate_metrics_serverapp.get(current_round, {})
        )
        round_results = {
            "round": current_round,
            "train_metrics": last_train_metrics,
            "evaluate_metrics_clientapp": last_eval_client_metrics,
            "evaluate_metrics_serverapp": last_eval_server_metrics,
        }
        results.append(round_results)
        # Save to JSON
        with open(f"{self.save_path}/results.json", "w", encoding="utf-8") as fp:
            json.dump(results, fp)

    def configure_train(
        self, server_round: int, arrays: ArrayRecord, config: ConfigRecord, grid: Grid
    ) -> Iterable[Message]:
        """Configure the next round using resource-score client selection.

        Each available node is assigned a score via::

            score = (α × battery) + (β × bandwidth) − (γ × past_failures)

        The top ``num_nodes`` nodes (determined by ``fraction_train``) are
        selected instead of the random sampling used in standard FedAvg.
        """
        # Perform basic learning rate scheduling
        if server_round == 3:  # half LR at round 3
            config["lr"] = config["lr"] * 0.5
            logger.log(INFO, "⚙️ Adjusted learning rate to %f", config["lr"])

        if self.fraction_train == 0.0:
            return []

        # Wait until the minimum number of nodes is available
        all_node_ids = list(grid.get_node_ids())
        while len(all_node_ids) < self.min_available_nodes:
            logger.log(
                INFO,
                "Waiting for nodes: %d connected (minimum: %d)",
                len(all_node_ids),
                self.min_available_nodes,
            )
            time.sleep(1)
            all_node_ids = list(grid.get_node_ids())

        # Determine how many nodes to select
        num_nodes = max(
            int(len(all_node_ids) * self.fraction_train), self.min_train_nodes
        )

        # Score every available node and sort by score (descending)
        scored_nodes = [
            (self._compute_resource_score(nid), nid) for nid in all_node_ids
        ]
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # Log per-node resource information
        logger.log(INFO, "📊 Resource scores for round %d:", server_round)
        for score, nid in scored_nodes:
            battery = self._simulate_battery(nid)
            bandwidth = self._simulate_bandwidth(nid)
            failures = self.past_failures.get(nid, 0)
            logger.log(
                INFO,
                "   Node %d → score=%.2f  "
                "(battery=%.1f%%, bandwidth=%.1f Mbps, failures=%d)",
                nid,
                score,
                battery,
                bandwidth,
                failures,
            )

        # Select the top-scoring nodes
        selected_node_ids = [nid for _, nid in scored_nodes[:num_nodes]]
        logger.log(
            INFO,
            "🎯 Resource-aware selection: %d/%d nodes selected "
            "(α=%.2f, β=%.2f, γ=%.2f)",
            len(selected_node_ids),
            len(all_node_ids),
            self.alpha,
            self.beta,
            self.gamma,
        )

        # Inject current server round into config (required by FedAvg protocol)
        config["server-round"] = server_round

        # Construct and return training messages for the selected nodes
        record = RecordDict(
            {self.arrayrecord_key: arrays, self.configrecord_key: config}
        )
        return self._construct_messages(record, selected_node_ids, MessageType.TRAIN)

    def aggregate_train(
        self,
        server_round: int,
        replies: Iterable[Message],
    ) -> tuple[ArrayRecord | None, MetricRecord | None]:
        """Aggregate training results and update per-node failure counts."""
        replies_list = list(replies)

        # Track failed nodes so their score is penalised in future rounds
        for msg in replies_list:
            if msg.has_error():
                node_id = msg.metadata.src_node_id
                self.past_failures[node_id] = self.past_failures.get(node_id, 0) + 1
                logger.log(
                    INFO,
                    "⚠️  Node %d failed (total failures: %d)",
                    node_id,
                    self.past_failures[node_id],
                )

        return super().aggregate_train(server_round, replies_list)

    def start(
        self,
        grid: Grid,
        initial_arrays: ArrayRecord,
        num_rounds: int = 3,
        timeout: float = 3600,
        train_config: Optional[ConfigRecord] = None,
        evaluate_config: Optional[ConfigRecord] = None,
        evaluate_fn: Optional[
            Callable[[int, ArrayRecord], Optional[MetricRecord]]
        ] = None,
    ) -> Result:
        """Execute the federated learning strategy logging results to W&B and saving
        them to disk."""

        # Init W&B
        wandb.init(project=PROJECT_NAME, name=f"{str(self.run_dir)}-ServerApp")

        # Keep track of best acc
        self.best_acc_so_far = 0.0

        log(INFO, "Starting %s strategy:", self.__class__.__name__)
        log_strategy_start_info(
            num_rounds, initial_arrays, train_config, evaluate_config
        )
        self.summary()
        log(INFO, "")

        # Initialize if None
        train_config = ConfigRecord() if train_config is None else train_config
        evaluate_config = ConfigRecord() if evaluate_config is None else evaluate_config
        result = Result()

        t_start = time.time()
        # Evaluate starting global parameters
        if evaluate_fn:
            res = evaluate_fn(0, initial_arrays)
            log(INFO, "Initial global evaluation results: %s", res)
            if res is not None:
                result.evaluate_metrics_serverapp[0] = res

        arrays = initial_arrays

        for current_round in range(1, num_rounds + 1):
            log(INFO, "")
            log(INFO, "[ROUND %s/%s]", current_round, num_rounds)

            # -----------------------------------------------------------------
            # --- TRAINING (CLIENTAPP-SIDE) -----------------------------------
            # -----------------------------------------------------------------

            # Call strategy to configure training round
            # Send messages and wait for replies
            train_replies = grid.send_and_receive(
                messages=self.configure_train(
                    current_round,
                    arrays,
                    train_config,
                    grid,
                ),
                timeout=timeout,
            )

            # Aggregate train
            agg_arrays, agg_train_metrics = self.aggregate_train(
                current_round,
                train_replies,
            )

            # Log training metrics and append to history
            if agg_arrays is not None:
                result.arrays = agg_arrays
                arrays = agg_arrays
            if agg_train_metrics is not None:
                log(INFO, "\t└──> Aggregated MetricRecord: %s", agg_train_metrics)
                result.train_metrics_clientapp[current_round] = agg_train_metrics
                # Log to W&B
                wandb.log(dict(agg_train_metrics), step=current_round)

            # -----------------------------------------------------------------
            # --- EVALUATION (CLIENTAPP-SIDE) ---------------------------------
            # -----------------------------------------------------------------

            # Call strategy to configure evaluation round
            # Send messages and wait for replies
            evaluate_replies = grid.send_and_receive(
                messages=self.configure_evaluate(
                    current_round,
                    arrays,
                    evaluate_config,
                    grid,
                ),
                timeout=timeout,
            )

            # Aggregate evaluate
            agg_evaluate_metrics = self.aggregate_evaluate(
                current_round,
                evaluate_replies,
            )

            # Log training metrics and append to history
            if agg_evaluate_metrics is not None:
                log(INFO, "\t└──> Aggregated MetricRecord: %s", agg_evaluate_metrics)
                result.evaluate_metrics_clientapp[current_round] = agg_evaluate_metrics
                # Log to W&B
                wandb.log(dict(agg_evaluate_metrics), step=current_round)
            # -----------------------------------------------------------------
            # --- EVALUATION (SERVERAPP-SIDE) ---------------------------------
            # -----------------------------------------------------------------

            # Centralized evaluation
            if evaluate_fn:
                log(INFO, "Global evaluation")
                res = evaluate_fn(current_round, arrays)
                log(INFO, "\t└──> MetricRecord: %s", res)
                if res is not None:
                    result.evaluate_metrics_serverapp[current_round] = res
                    # Maybe save to disk if new best is found
                    self._update_best_acc(current_round, res["accuracy"], arrays)
                    # Log to W&B
                    wandb.log(dict(res), step=current_round)

            # Save metrics to disk as JSON
            self.save_metrics_as_json(current_round=current_round, result=result)

        log(INFO, "")
        log(INFO, "Strategy execution finished in %.2fs", time.time() - t_start)
        log(INFO, "")
        log(INFO, "Final results:")
        log(INFO, "")
        for line in io.StringIO(str(result)):
            log(INFO, "\t%s", line.strip("\n"))
        log(INFO, "")

        return result
