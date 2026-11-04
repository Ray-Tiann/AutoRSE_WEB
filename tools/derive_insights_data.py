#!/usr/bin/env python3
"""Derive historical API resources from bounded trial-result metadata only.

No native trajectory, model credential, private label, or uploaded prediction is
read. Never infer missing prices or allocate GPU/reimbursement expenses.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


TASKS = ("hstu", "intsr", "tiger", "onetrans", "rankmixer", "wukong")
CONFIGS = (
    ("DPSKflash", "ClaudeCode", "claude-code-deepseek-v4-flash", "Claude Code", "DeepSeek V4 Flash"),
    ("Opus48", "ClaudeCode", "claude-code-claude-opus-4-8", "Claude Code", "Claude Opus 4.8"),
    ("DPSKflash", "Codex", "codex-deepseek-v4-flash", "Codex", "DeepSeek V4 Flash"),
    ("GPT55", "Codex", "codex-gpt-5-5", "Codex", "GPT-5.5"),
    ("DPSKflash", "Terminus2", "terminus-2-deepseek-v4-flash", "Terminus-2", "DeepSeek V4 Flash"),
    ("GPT55", "Terminus2", "terminus-2-gpt-5-5", "Terminus-2", "GPT-5.5"),
    ("Opus48", "Terminus2", "terminus-2-claude-opus-4-8", "Terminus-2", "Claude Opus 4.8"),
)
LOOKUP = {(m, h): {"config_id": key, "harness": harness, "model": model}
          for m, h, key, harness, model in CONFIGS}
CANONICAL = Path("reports/action-statistics-all125-20261019/run_coverage.csv")
PAPER = Path("output/autorse-web-maintenance-20261102/checkout/assets/js/data.js")
RESULTS = Path("experiment-records/trajectory/results")


def fingerprint(root, path):
    label = path.relative_to(root).as_posix() if path.is_relative_to(root) else "reference/" + path.name
    return {"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def bounded_json(path):
    assert path.name == "result.json" and not path.is_symlink() and path.stat().st_size <= 2_000_000
    return json.loads(path.read_text())


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def mean(values):
    return statistics.mean(values) if values else None


def sd(values):
    return statistics.stdev(values) if len(values) > 1 else None


def duration(execution):
    start, finish = execution.get("started_at"), execution.get("finished_at")
    if not isinstance(start, str) or not isinstance(finish, str):
        return None
    first, last = (datetime.fromisoformat(v.replace("Z", "+00:00")) for v in (start, finish))
    if first.tzinfo is None or last.tzinfo is None:
        return None
    seconds = (last - first).total_seconds()
    assert seconds >= 0
    return seconds


def summarize(rows, baseline):
    paired = [r for r in rows if r["cost_usd"] is not None and r["score"] is not None]
    scores = [r["score"] for r in rows if r["score"] is not None]
    costs = [r["cost_usd"] for r in paired]
    paired_scores = [r["score"] for r in paired]
    return {
        "runs": len(rows), "cost_recorded_runs": len(paired),
        "cost_coverage": f"{len(paired)}/{len(rows)}", "cost_complete": len(paired) == len(rows),
        "all_score_mean": mean(scores), "all_score_sd": sd(scores),
        "reported_cost_sum_usd": sum(costs) if costs else None,
        "paired_mean_cost_usd": mean(costs), "paired_sd_cost_usd": sd(costs),
        "paired_score_mean": mean(paired_scores), "paired_score_sd": sd(paired_scores),
        "paired_relative_gain_percent": 100 * (mean(paired_scores) / baseline - 1) if paired_scores else None,
        "paired_run_ids": [r["run_id"] for r in paired],
        "missing_cost_run_ids": [r["run_id"] for r in rows if r["cost_usd"] is None],
    }


def aggregate_tasks(task_summaries, selected):
    summaries = [task_summaries[t] for t in selected]
    present = sum(s["cost_recorded_runs"] > 0 for s in summaries)
    eligible = present == len(selected)
    return {
        "task_ids": list(selected), "paired_task_count": present, "task_count": len(selected),
        "eligible": eligible,
        "paired_runs": sum(s["cost_recorded_runs"] for s in summaries),
        "runs": sum(s["runs"] for s in summaries),
        "cost_complete": eligible and all(s["cost_complete"] for s in summaries),
        "mean_cost_usd_per_task_run": mean([s["paired_mean_cost_usd"] for s in summaries]) if eligible else None,
        "mean_relative_gain_percent": mean([s["paired_relative_gain_percent"] for s in summaries]) if eligible else None,
    }


def build(root, *, canonical=CANONICAL, paper=PAPER):
    source = root / RESULTS
    canonical_path, paper_path = (root / canonical).resolve(), (root / paper).resolve()
    with canonical_path.open(encoding="utf-8-sig", newline="") as stream:
        coverage = list(csv.DictReader(stream))
    assert len(coverage) == len({r["run_id"] for r in coverage}) == 125
    expected = {root / Path(r["trajectory"]).parent.parent / "result.json" for r in coverage}
    observed = set(source.glob("*/*/*_task__*/result.json"))
    assert expected == observed, "Metadata inventory differs from the frozen 125-native-run manifest"
    website = json.loads(paper_path.read_text().split("=", 1)[1].strip().rstrip(";"))["mainResults"]
    assert tuple(t.lower() for t in website["task_order"]) == TASKS
    baselines = dict(zip(TASKS, website["baseline"]))
    paper_rows = {(r["harness"], r["model"]): r for r in website["rows"]}
    assert len(paper_rows) == 7
    runs = []
    for path in sorted(expected):
        group, task, trial_name = path.parts[-4:-1]
        group_match = re.fullmatch(r"(DPSKflash|GPT55|Opus48)_(ClaudeCode|Codex|Terminus2)_t([123])_[0-9]{4}", group)
        assert group_match and task in TASKS
        m, h, trial = group_match.groups()
        identity = LOOKUP[(m, h)]
        data = bounded_json(path)
        assert data.get("exception_info") is None and data["trial_name"] == trial_name
        result = data["agent_result"]
        rewards = data["verifier_result"]["rewards"]
        metric = "ndcg_at_10" if task in ("hstu", "tiger") else "macro_ndcg_at_10" if task == "intsr" else "auc"
        score = number(rewards.get("reward"))
        assert score is not None
        cost = number(result.get("cost_usd"))
        assert cost is None or cost >= 0
        execution = data.get("agent_execution") or {}
        tokens = {k: number(result.get(k)) for k in ("n_input_tokens", "n_cache_tokens", "n_output_tokens")}
        assert all(type(v) is int and v >= 0 for v in tokens.values())
        runs.append({**identity, "run_id": group + "::" + task, "task": task, "trial": int(trial),
                     "trial_name": trial_name, "model_name_reported": data["config"]["agent"]["model_name"],
                     "source": fingerprint(root, path), "cost_usd": cost, "cost_kind": "harness_reported_usd",
                     "score": score, "metric": metric, "tokens": tokens,
                     "agent_execution_started_at": execution.get("started_at"),
                     "agent_execution_finished_at": execution.get("finished_at"),
                     "agent_execution_duration_seconds": duration(execution)})
    assert len(runs) == 125 and sum(r["cost_usd"] is not None for r in runs) == 101

    # Outer job aggregates duplicate trial metadata; only retain the unmatched
    # aggregate as a documented exclusion, never as a synthetic extra native run.
    inner_keys = {r["run_id"] for r in runs}
    excluded = []
    outer = list(source.glob("*/*/result.json"))
    assert len(outer) == 126
    for path in sorted(outer):
        group, task = path.parts[-3:-1]
        if group + "::" + task in inner_keys:
            continue
        data = bounded_json(path)
        stats = data.get("stats") or {}
        scores = [number(x.get("reward")) for e in stats.get("evals", {}).values() for x in e.get("metrics", [])]
        excluded.append({"run_id": group + "::" + task, "source": fingerprint(root, path),
                         "reason": "Only an outer job aggregate exists; no trial-level result or native session in the canonical 125-run manifest. Do not treat the aggregate as an independently preserved run.",
                         "aggregate_cost_usd": number(stats.get("cost_usd")), "aggregate_scores": scores})
    assert [r["run_id"] for r in excluded] == ["GPT55_Terminus2_t2_0816::onetrans"]

    configs, comparisons = [], []
    for m, h, config_id, harness, model in CONFIGS:
        rows = [r for r in runs if r["config_id"] == config_id]
        expected_count = 17 if config_id == "terminus-2-gpt-5-5" else 18
        assert len(rows) == expected_count
        tasks = {task: summarize([r for r in rows if r["task"] == task], baselines[task]) for task in TASKS}
        published = paper_rows[(harness, model)]
        for i, task in enumerate(TASKS):
            current = tasks[task]
            checks = {"config_id": config_id, "task": task, "runs": current["runs"],
                      "derived_mean": current["all_score_mean"], "derived_sample_sd": current["all_score_sd"],
                      "paper_mean": published["scores"][i], "paper_sample_sd": published["sd"][i]}
            checks["matches_at_four_decimals"] = (round(checks["derived_mean"], 4) == checks["paper_mean"]
                                                    and round(checks["derived_sample_sd"], 4) == checks["paper_sample_sd"])
            comparisons.append(checks)
        known = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
        configs.append({"config_id": config_id, "harness": harness, "model": model,
                        "runs": len(rows), "cost_recorded_runs": len(known), "cost_coverage": f"{len(known)}/{len(rows)}",
                        "reported_cost_sum_usd": sum(known), "recorded_run_mean_cost_usd": mean(known),
                        "tasks": tasks, "overall_paired": aggregate_tasks(tasks, TASKS),
                        "common_tasks_paired": aggregate_tasks(tasks, ("tiger", "rankmixer"))})
    mismatches = [c for c in comparisons if not c["matches_at_four_decimals"]]
    assert len(mismatches) == 1 and mismatches[0]["config_id"] == "terminus-2-gpt-5-5" and mismatches[0]["task"] == "onetrans"

    derived = {"schema_version": 1, "dataset": "historical-paper-resource-audit-125-native-runs",
               "task_order": list(TASKS), "baselines": baselines,
               "metric_direction": "higher_is_better", "cost_direction": "lower_is_better",
               "cost_kind": "harness_reported_usd", "cost_currency": "USD", "repriced_or_imputed": False,
               "cost_definition": "Copied without repricing from each trial result's agent_result.cost_usd. Harness-reported accounting, not a verified provider invoice. Null remains unknown; zero is never substituted. GPU/server expenses and reimbursement totals are excluded.",
               "pairing_definition": "A point uses cost and score from the identical run subset. Per task, compute paired means. Overall requires a nonempty paired subset for each of all six tasks and averages the six task means equally, for both cost and relative score gain. Relative gain uses the published four-decimal baselines. No raw AUC/NDCG averaging.",
               "duration_definition": "Recorded agent_execution.finished_at minus started_at, only when both carry explicit time zones. This is wall-clock agent execution duration, not GPU busy time or billed GPU-hours.",
               "token_definition": "The three token counters are copied verbatim from the harness. Cached input is a subset reported separately, not an extra input count. Different adapters may use different accounting; no price is inferred from tokens.",
               "source_manifest": fingerprint(root, canonical_path), "paper_source": fingerprint(root, paper_path),
               "runs_count": len(runs), "cost_recorded_runs": 101, "missing_cost_runs": 24,
               "configs": configs, "runs": runs, "excluded_aggregate_only": excluded,
               "paper_validation": {"cells": 42, "matching_cells_at_four_decimals": 41, "mismatches": mismatches,
                   "note": "Preserve the current published table. The canonical native subset has OneTrans/T2-GPT t1+t3; the paper mean/SD match t1 plus the excluded t2 outer-only aggregate. No costs exist for these OneTrans runs, so no cost-score point is fabricated."},
               "limitations": [
                   "Historical paper results and the sanitized public-v2 release are different data revisions; these are not new public-v2 evaluations.",
                   "Reported API costs may reflect historical provider/adapter pricing and cache semantics; the project has not verified invoices or repriced all providers uniformly.",
                   "Both GPT-5.5 configurations have costs for TIGER and RankMixer only. Their six-task overall cost/gain points are unavailable.",
                   "Claude Code/DeepSeek HSTU trial 3 has unknown cost; that task's paired point uses trials 1 and 2 only and is visibly marked 2/3.",
                   "Original native trajectories and private targets are not copied or read by this derivation. Source hashes apply to bounded result metadata only.",
               ]}
    audit = {"passed": True, "canonical_native_runs": 125, "outer_job_aggregates": 126,
             "excluded_aggregate_only_count": 1, "cost_known_runs": 101, "cost_unknown_runs": 24,
             "tokens_known_runs": 125, "duration_known_runs": sum(r["agent_execution_duration_seconds"] is not None for r in runs),
             "paper_cells_matching": 41, "paper_cells_mismatching": 1, "paper_mismatches": mismatches,
             "six_task_paired_config_count": sum(c["overall_paired"]["eligible"] for c in configs),
             "common_tiger_rankmixer_config_count": sum(c["common_tasks_paired"]["eligible"] for c in configs),
             "native_trajectories_read": 0, "private_inputs_read": 0, "sources_rewritten": False}
    return derived, audit


def frontend_data(derived, audit):
    """The chart's x/y/error bar always refer to the same paired observations."""
    names = {"hstu": "HSTU", "intsr": "IntSR", "tiger": "TIGER", "onetrans": "OneTrans",
             "rankmixer": "RankMixer", "wukong": "WuKong"}
    metrics = {"hstu": "NDCG@10", "intsr": "Macro NDCG@10", "tiger": "NDCG@10",
               "onetrans": "Click AUC", "rankmixer": "AUC", "wukong": "AUC"}
    scopes = {}
    for task in TASKS:
        rows = []
        for config in derived["configs"]:
            summary = config["tasks"][task]
            recorded, total = summary["cost_recorded_runs"], summary["runs"]
            rows.append({"id": config["config_id"], "model": config["model"], "harness": config["harness"],
                         "cost_usd": summary["paired_mean_cost_usd"], "cost_sd": summary["paired_sd_cost_usd"],
                         "score": summary["paired_score_mean"], "score_sd": summary["paired_score_sd"],
                         "recorded_runs": recorded, "total_runs": total,
                         "status": "complete" if recorded == total else "partial" if recorded else "unavailable",
                         "covered_tasks": int(recorded > 0), "total_tasks": 1,
                         "paired_run_ids": summary["paired_run_ids"]})
        scopes[names[task]] = {"label": names[task], "metric": metrics[task], "quality_label": metrics[task],
                              "baseline": derived["baselines"][task], "rows": rows}
    rows = []
    for config in derived["configs"]:
        summary = config["overall_paired"]
        rows.append({"id": config["config_id"], "model": config["model"], "harness": config["harness"],
                     "cost_usd": summary["mean_cost_usd_per_task_run"], "cost_sd": None,
                     "score": summary["mean_relative_gain_percent"], "score_sd": None,
                     "recorded_runs": summary["paired_runs"], "total_runs": summary["runs"],
                     "status": "unavailable" if not summary["eligible"] else "complete" if summary["cost_complete"] else "partial",
                     "covered_tasks": summary["paired_task_count"], "total_tasks": 6})
    scopes["overall"] = {"label": "Overall · six tasks", "metric": "mean_relative_gain_percent",
                         "quality_label": "Mean relative gain (%) · matched runs", "baseline": 0,
                         "rows": rows}
    return {"schema_version": 1, "currency": "USD", "cost_definition": derived["cost_definition"],
            "pairing_definition": derived["pairing_definition"],
            "coverage_definition": "recorded_runs counts runs containing both a reported API cost and a verifier score. total_runs counts canonical native sessions, not nominal 3-trial budgets. Complete means all observed runs have a cost. Partial means some are missing; overall unavailable means one or more tasks have no paired records.",
            "cost_axis_label": "Mean reported API cost per task run (USD)",
            "baselines": {names[t]: derived["baselines"][t] for t in TASKS},
            "scopes": scopes,
            "sources": {"canonical_manifest": derived["source_manifest"], "paper_reference": derived["paper_source"],
                        "run_level_csv": derived["run_level_csv"],
                        "trial_result_metadata": [r["source"] for r in derived["runs"]]},
            "audit": {k: audit[k] for k in ("passed", "canonical_native_runs", "outer_job_aggregates",
                      "cost_known_runs", "cost_unknown_runs", "tokens_known_runs", "duration_known_runs",
                      "paper_cells_matching", "paper_cells_mismatching", "paper_mismatches",
                      "six_task_paired_config_count", "native_trajectories_read", "private_inputs_read")},
            "limitations": derived["limitations"]}


def write_public_csv(derived, output):
    fields = ("run_id", "config_id", "harness", "model", "task", "trial", "cost_usd", "score", "metric",
              "n_input_tokens", "n_cache_tokens", "n_output_tokens", "agent_execution_duration_seconds",
              "source_metadata_path", "source_metadata_sha256")
    path = output / "paper-run-resources.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in derived["runs"]:
            value = {field: row[field] for field in fields if field in row}
            value.update(row["tokens"], source_metadata_path=row["source"]["path"],
                         source_metadata_sha256=row["source"]["sha256"])
            # Explicit null is unknown, never a free run or an inferred API price.
            writer.writerow({k: "null" if v is None else v for k, v in value.items()})
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": 125}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", "--root", dest="root", type=Path, default=Path.cwd(),
                        help="Research archive root with experiment-records/ and the canonical coverage manifest")
    parser.add_argument("--coverage-manifest", type=Path, default=CANONICAL,
                        help="CSV inventory, relative to the workspace root unless absolute")
    parser.add_argument("--paper-reference", type=Path,
                        help="Published assets/js/data.js; defaults to this website's asset when installed under tools/")
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination for sanitized derived JSON/CSV and audit")
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    adjacent_paper = Path(__file__).resolve().parents[1] / "assets/js/data.js"
    paper = args.paper_reference or (adjacent_paper if adjacent_paper.is_file() else PAPER)
    derived, audit = build(root, canonical=args.coverage_manifest, paper=paper)
    derived["run_level_csv"] = write_public_csv(derived, output)
    target = output / "paper-resources-derived.json"
    target.write_text(json.dumps(derived, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    audit["derived_file_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    audit["public_csv_sha256"] = derived["run_level_csv"]["sha256"]
    insights = output / "insights-data.json"
    insights.write_text(json.dumps(frontend_data(derived, audit), ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    audit["insights_file_sha256"] = hashlib.sha256(insights.read_bytes()).hexdigest()
    audit["derivation_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / "paper-resources-audit.json").write_text(json.dumps(audit, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
