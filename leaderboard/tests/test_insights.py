"""Independent invariants for the shipped cost and six-task chart code."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "hf-leaderboard"
TASKS = ("HSTU", "IntSR", "TIGER", "OneTrans", "RankMixer", "WuKong")
PAPER_SCIENTIFIC_SHA256 = "f8d4e8d5356458d5d6f8f1bd8935ec53db9c176f109922f7241b6e3dee2c2082"


def paper_data():
    html = (BOARD / "index.html").read_text()
    return json.loads(re.search(r'id="seed-data">(.*?)</script>', html, re.S).group(1))


def scientific_values(paper):
    return {"task_order": paper["task_order"],
            "tasks": [{"name": task["name"], "metric": task["metric"],
                       "baseline_score": task["baseline_score"]} for task in paper["tasks"]],
            "rows": [{key: row[key] for key in
                      ("id", "scores", "sd", "trial_counts", "relative_gain_percent", "average_gain_percent")}
                     for row in sorted(paper["rows"], key=lambda row: row["id"])]}


def cost_row(identifier, cost, score, **updates):
    row = {"id": identifier, "model": identifier, "harness": "Synthetic harness",
           "cost_usd": cost, "score": score, "cost_sd": None, "score_sd": None,
           "recorded_runs": 3, "total_runs": 3, "status": "complete",
           "covered_tasks": 1, "total_tasks": 1}
    row.update(updates)
    return row


def cost_fixture():
    return {"schema_version": 1, "cohort": "paper", "currency": "USD", "scopes": {
        "TIGER": {"label": "TIGER", "metric": "NDCG@10", "quality_label": "NDCG@10", "rows": [
            cost_row("free", 0, .2), cost_row("a", 1, .5), cost_row("twin", 1, .5),
            cost_row("lower-at-same-cost", 1, .4), cost_row("good", 2, .7),
            cost_row("flat", 3, .7), cost_row("bad", 4, .3), cost_row("more", 6, .9),
            cost_row("missing", None, None, recorded_runs=0, status="unavailable", covered_tasks=0),
            cost_row("negative", -1, .8), cost_row("not-numeric", True, .8),
        ]}}}


def profile_fixture():
    board = copy.deepcopy(paper_data())
    board["rows"] = []
    for identifier, scores in (
        ("a", [.1, .3, 0, .5, .6, .7]),
        ("b", [.2, None, .2, .4, .3, .8]),
        ("c", [.4, .6, .4, .8, .9, 1]),
    ):
        board["rows"].append({"id": identifier, "model": identifier, "harness": "Synthetic harness",
                              "scores": scores, "sd": [.01] * 6, "trial_counts": [3] * 6,
                              "provenance": "Paper reference"})
    return board


class InsightsEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((BOARD / "insights-data.json").read_text())
        cls.paper = paper_data()

    def test_all_42_original_scientific_cells_are_unchanged(self):
        scientific = scientific_values(self.paper)
        digest = hashlib.sha256(json.dumps(scientific, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, PAPER_SCIENTIFIC_SHA256)
        self.assertEqual(sum(len(row["scores"]) for row in scientific["rows"]), 42)

    def test_recorded_coverage_is_125_native_runs_not_126_job_aggregates(self):
        rows = [row for task in TASKS for row in self.data["scopes"][task]["rows"]]
        self.assertEqual(sum(row["total_runs"] for row in rows), 125)
        self.assertEqual(sum(row["recorded_runs"] for row in rows), 101)
        self.assertEqual(self.data["audit"]["canonical_native_runs"], 125)
        self.assertEqual(self.data["audit"]["cost_known_runs"], 101)
        self.assertEqual(self.data["currency"], "USD")
        self.assertIn("not a verified", self.data["cost_definition"].lower())

    def test_tiger_and_rankmixer_have_complete_seven_configuration_costs(self):
        for task in ("TIGER", "RankMixer"):
            with self.subTest(task=task):
                rows = self.data["scopes"][task]["rows"]
                self.assertEqual(len(rows), 7)
                self.assertEqual({row["id"] for row in rows}, {row["id"] for row in self.paper["rows"]})
                for row in rows:
                    self.assertEqual((row["recorded_runs"], row["total_runs"], row["status"]), (3, 3, "complete"))
                    self.assertGreater(row["cost_usd"], 0)
                    self.assertTrue(math.isfinite(row["score"]))

    def test_public_run_csv_reconstructs_the_paired_chart_values(self):
        source = self.data["sources"]["run_level_csv"]
        blob = (BOARD / source["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), source["sha256"])
        rows = list(csv.DictReader(blob.decode().splitlines()))
        self.assertEqual(len(rows), source["rows"])
        self.assertEqual(len({row["run_id"] for row in rows}), 125)
        expected_fields = {"run_id", "config_id", "harness", "model", "task", "trial",
                           "cost_usd", "score", "metric", "n_input_tokens", "n_cache_tokens",
                           "n_output_tokens", "agent_execution_duration_seconds",
                           "source_metadata_path", "source_metadata_sha256"}
        self.assertEqual(set(rows[0]), expected_fields)
        for task in TASKS:
            for point in self.data["scopes"][task]["rows"]:
                with self.subTest(task=task, configuration=point["id"]):
                    trials = [row for row in rows
                              if row["task"] == task.lower() and row["config_id"] == point["id"]]
                    paired = [row for row in trials
                              if row["cost_usd"] not in ("", "null") and row["score"] not in ("", "null")]
                    self.assertEqual(point["total_runs"], len(trials))
                    self.assertEqual(set(point["paired_run_ids"]), {row["run_id"] for row in paired})
                    for field, sd_field in (("cost_usd", "cost_sd"), ("score", "score_sd")):
                        values = [float(row[field]) for row in paired]
                        if not values:
                            self.assertIsNone(point[field])
                            self.assertIsNone(point[sd_field])
                            continue
                        self.assertAlmostEqual(point[field], statistics.mean(values), places=12)
                        self.assertAlmostEqual(point[sd_field], statistics.stdev(values), places=12)

    def test_unknown_gpt_costs_and_partial_hstu_are_not_imputed(self):
        for task in ("HSTU", "IntSR", "OneTrans", "WuKong"):
            indexed = {row["id"]: row for row in self.data["scopes"][task]["rows"]}
            for identifier in ("codex-gpt-5-5", "terminus-2-gpt-5-5"):
                row = indexed[identifier]
                self.assertIsNone(row["cost_usd"])
                self.assertIsNone(row["score"])
                self.assertEqual(row["recorded_runs"], 0)
                self.assertEqual(row["status"], "unavailable")
        hstu = {row["id"]: row for row in self.data["scopes"]["HSTU"]["rows"]}
        partial = hstu["claude-code-deepseek-v4-flash"]
        self.assertEqual((partial["recorded_runs"], partial["total_runs"], partial["status"]), (2, 3, "partial"))
        self.assertEqual(len(partial["paired_run_ids"]), 2)

    def test_overall_uses_equal_task_paired_means_not_raw_auc_ndcg_average(self):
        scopes = self.data["scopes"]
        per_task = {task: {row["id"]: row for row in scopes[task]["rows"]} for task in TASKS}
        available = 0
        for row in scopes["overall"]["rows"]:
            paired = [per_task[task][row["id"]] for task in TASKS]
            usable = [item for item in paired if item["cost_usd"] is not None and item["score"] is not None]
            self.assertEqual(row["covered_tasks"], len(usable))
            self.assertEqual(row["recorded_runs"], sum(item["recorded_runs"] for item in paired))
            if len(usable) < 6:
                self.assertIsNone(row["cost_usd"])
                self.assertIsNone(row["score"])
                self.assertEqual(row["status"], "unavailable")
                continue
            available += 1
            expected_cost = math.fsum(item["cost_usd"] for item in paired) / 6
            expected_gain = 100 * math.fsum(
                per_task[task][row["id"]]["score"] / self.data["baselines"][task] - 1 for task in TASKS) / 6
            self.assertAlmostEqual(row["cost_usd"], expected_cost, places=12)
            self.assertAlmostEqual(row["score"], expected_gain, places=10)
            self.assertIsNone(row["score_sd"])
            self.assertIsNone(row["cost_sd"])
            self.assertNotAlmostEqual(row["score"], math.fsum(item["score"] for item in paired) / 6, places=3)
        self.assertEqual(available, 5)

    def test_historical_discrepancy_is_explicit_and_not_used_as_a_cost_point(self):
        audit = self.data["audit"]
        self.assertEqual((audit["paper_cells_matching"], audit["paper_cells_mismatching"]), (41, 1))
        mismatch = audit["paper_mismatches"][0]
        self.assertEqual((mismatch["config_id"], mismatch["task"]), ("terminus-2-gpt-5-5", "onetrans"))
        self.assertEqual((mismatch["paper_mean"], mismatch["paper_sample_sd"]), (.7285, .0498))
        row = next(row for row in self.data["scopes"]["OneTrans"]["rows"] if row["id"] == mismatch["config_id"])
        self.assertIsNone(row["cost_usd"])


@unittest.skipUnless(shutil.which("node"), "Node is required for chart behavior checks")
class InsightsCoreTests(unittest.TestCase):
    def run_node(self, body, payload=None):
        source = BOARD / "insights.js"
        script = "const api=require(" + json.dumps(str(source)) + "),data=" + json.dumps(payload) + ";\n"
        script += body
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_pareto_requires_strict_domination_and_keeps_zero_and_exact_ties(self):
        result = self.run_node("""
const rows=api.costRows(data,'paper','TIGER');
console.log(JSON.stringify({frontier:api.paretoFrontier(rows).map(row=>row.id),
 same:api.dominatedBy(rows.find(r=>r.id==='a'),rows.find(r=>r.id==='twin')),
 costly:api.dominatedBy(rows.find(r=>r.id==='flat'),rows.find(r=>r.id==='good')),
 cheaper:api.dominatedBy(rows.find(r=>r.id==='good'),rows.find(r=>r.id==='flat'))}));
""", cost_fixture())
        self.assertEqual(set(result["frontier"]), {"free", "a", "twin", "good", "more"})
        self.assertEqual((result["same"], result["costly"], result["cheaper"]), (False, True, False))

    def test_cost_rank_is_ascending_with_zero_ties_and_missing_separate(self):
        result = self.run_node("""
const rows=api.costRows(data,'paper','TIGER'),rank=api.costRanking(rows);
console.log(JSON.stringify({ranked:rank.ranked.map(row=>[row.id,row.cost_usd,row.rank]),
 missing:rank.missing.map(row=>row.id),zero:rows.find(row=>row.id==='free').available,
 zeroLabel:api.formatCost(0),missingLabel:api.formatCost(null)}));
""", cost_fixture())
        ranked = result["ranked"]
        self.assertEqual([row[1] for row in ranked], [0, 1, 1, 1, 2, 3, 4, 6])
        self.assertEqual([row[2] for row in ranked], [1, 2, 2, 2, 5, 6, 7, 8])
        self.assertEqual(set(result["missing"]), {"missing", "negative", "not-numeric"})
        self.assertTrue(result["zero"])
        self.assertIn("0", result["zeroLabel"])
        self.assertRegex(result["missingLabel"], r"N/A|[Uu]navailable|[Nn]ot recorded")

    def test_cost_quality_keeps_paired_score_instead_of_full_paper_mean(self):
        fixture = cost_fixture()
        board = profile_fixture()
        board["rows"] = [dict(board["rows"][0], id="a", scores=[.999] * 6)]
        result = self.run_node("""
console.log(JSON.stringify(api.costRows(data.cost,'paper','TIGER',data.board)));
""", {"cost": fixture, "board": board})
        self.assertEqual([row["id"] for row in result], ["a"])
        self.assertEqual(result[0]["score"], .5)

    def test_community_never_inherits_paper_costs_even_for_same_named_id(self):
        community = profile_fixture()
        community["metadata"]["provenance"] = "Reviewed community"
        for row in community["rows"]:
            row["provenance"] = "Reviewed community"
        result = self.run_node("""
const rows=api.costRows(data.cost,'community','TIGER',data.board);
console.log(JSON.stringify(rows));
""", {"cost": cost_fixture(), "board": community})
        self.assertTrue(all(not row["available"] for row in result))
        self.assertTrue(all(row.get("cost_usd") is None for row in result))
        community["rows"] = []
        empty = self.run_node("console.log(JSON.stringify(api.costRows(data.cost,'community','TIGER',data.board)));",
                              {"cost": cost_fixture(), "board": community})
        self.assertEqual(empty, [])

    def test_profile_uses_full_cohort_reference_and_preserves_missing_vs_zero(self):
        result = self.run_node("""
console.log(JSON.stringify({references:api.normalizationReferences(data),
 ab:api.profileData(data,['a','b']),ac:api.profileData(data,['a','c'])}));
""", profile_fixture())
        self.assertEqual(result["references"], [.4, .6, .4, .8, .9, 1])
        ab = {series["id"]: series for series in result["ab"]["series"]}
        ac = {series["id"]: series for series in result["ac"]["series"]}
        self.assertEqual(ab["a"]["values"], ac["a"]["values"])
        self.assertEqual(ab["b"]["values"][1], None)
        self.assertEqual(ab["a"]["values"][2], 0)
        self.assertEqual(ab["a"]["raw"], [.1, .3, 0, .5, .6, .7])
        self.assertEqual(ab["a"]["sd"], [.01] * 6)
        self.assertEqual(ab["a"]["trials"], [3] * 6)
        for actual, expected in zip(ab["a"]["values"], [25, 50, 0, 62.5, 200 / 3, 70]):
            self.assertAlmostEqual(actual, expected)

    def test_zero_or_missing_reference_does_not_create_infinite_or_fake_zero_profile(self):
        board = profile_fixture()
        for row in board["rows"]:
            row["scores"][0] = 0
            row["scores"][1] = None
        result = self.run_node("console.log(JSON.stringify(api.profileData(data,['a','b'])));", board)
        for series in result["series"]:
            self.assertIsNone(series["values"][0])
            self.assertIsNone(series["values"][1])

    def test_core_does_not_mutate_frozen_inputs(self):
        result = self.run_node("""
function freeze(x){if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;}
freeze(data);const before=JSON.stringify(data);
const rows=api.costRows(data.cost,'paper','TIGER');freeze(rows);
api.costRanking(rows);api.paretoFrontier(rows);api.profileData(data.board,['a','b']);api.normalizationReferences(data.board);
console.log(JSON.stringify(JSON.stringify(data)===before));
""", {"cost": cost_fixture(), "board": profile_fixture()})
        self.assertTrue(result)


class InsightsReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("autorse_insights_release_builder", ROOT / "selfhost/build_release.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def test_insight_assets_are_in_release_manifest_and_tampering_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="autorse-insights-build-") as folder:
            output = Path(folder) / "release"
            manifest = self.builder.build(output, origin="https://114.66.48.196")
            indexed = {row["path"]: row for row in manifest["files"]}
            for name in self.builder.INSIGHT_ASSETS:
                relative = "public/leaderboard/" + name
                blob = (BOARD / name).read_bytes()
                self.assertEqual((output / relative).read_bytes(), blob)
                self.assertEqual(indexed[relative]["sha256"], hashlib.sha256(blob).hexdigest())
            self.assertFalse(manifest["private_data_included"])
            self.assertFalse(manifest["secret_keys_included"])
            self.builder.verify(output)
            (output / "public/leaderboard/insights-data.json").write_text('{"changed": true}')
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
                self.builder.verify(output)

    def test_builder_uses_explicit_insight_allowlist_and_refuses_asset_symlinks(self):
        with tempfile.TemporaryDirectory(prefix="autorse-insights-source-") as folder:
            root = Path(folder)
            source = root / "source"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"))
            unlisted = source / "hf-leaderboard/not-a-public-asset.txt"
            unlisted.write_text("private maintenance material must not enter web root")
            output = root / "release"
            manifest = self.builder.build(output, origin="https://114.66.48.196", source=source)
            self.assertFalse(any("not-a-public-asset" in row["path"] for row in manifest["files"]))
            (source / "hf-leaderboard/insights-data.json").unlink()
            (source / "hf-leaderboard/insights-data.json").symlink_to(unlisted)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.builder.build(root / "bad-release", origin="https://114.66.48.196", source=source)
            self.assertFalse((root / "bad-release").exists())


if __name__ == "__main__":
    unittest.main()
