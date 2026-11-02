"""Execute the shipped presentation and control code with synthetic submissions."""
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autorse_leaderboard.ranking import build_leaderboard, DATA_REVISION


def community_fixture():
    # The large HSTU lead gives `spiky` the highest raw-score average, but it
    # loses the other five tasks. This detects accidental averaging of metrics.
    rows = []
    for identifier, scores in (("spiky", [.99, .51, .051, .67, .8, .96]),
                               ("balanced", [.01, .52, .052, .68, .81, .97]),
                               ("tied", [.01, .52, .052, .68, .81, .97])):
        rows.append({"id": identifier, "participant": "synthetic", "kind": "benchmark",
                     "publishable": True, "data_revision": DATA_REVISION,
                     "configuration": {"model": identifier, "harness": "Synthetic harness"},
                     "scores": scores, "sd": [.00004, .00005, .003, .01025, 0, .0000999],
                     "trial_counts": [3] * 6, "source_url": ""})
    return build_leaderboard(rows)


def four(value):
    return format(Decimal(str(value)).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP), ".4f")


@unittest.skipUnless(shutil.which("node"), "Node is required for frontend behavior checks")
class FrontendPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = (Path(__file__).resolve().parents[2] / "hf-leaderboard/index.html").read_text()
        cls.paper = json.loads(re.search(r'<script type="application/json" id="seed-data">(.*?)</script>', html, re.S).group(1))
        cls.empty = json.loads(re.search(r'<script type="application/json" id="community-seed-data">(.*?)</script>', html, re.S).group(1))
        scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
        cls.core = next(script for script in scripts if script.startswith("(function(root,factory)"))
        cls.controls = scripts[-1]
        cls.element_ids = re.findall(r'\bid="([^"]+)"', html)

    def run_node(self, body, payload=None, browser=False):
        payload = payload or {"paper": self.paper, "empty": self.empty, "community": community_fixture()}
        if browser:
            payload = {**payload, "element_ids": self.element_ids}
        script = "const module={exports:{}};\n" + self.core
        script += "\nconst api=module.exports,data=" + json.dumps(payload) + ";\n"
        if browser:
            script += r'''
// A small DOM adapter executes the real controls/render script. It provides
// browser operations, not a second implementation of leaderboard behavior.
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.value='';this._text='';this.className='';this.classes=new Set();this.classList={add:x=>this.classes.add(x),toggle:(x,on)=>on?this.classes.add(x):this.classes.delete(x)};}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this._text='';this.children=[...children];}
  setAttribute(name,value){this.attributes[name]=String(value);}
  addEventListener(type,callback){(this.listeners[type]??=[]).push(callback);}
  dispatch(type){for(const callback of this.listeners[type]??[])callback({target:this});}
}
const nodes=new Map(data.element_ids.map(id=>[id,new Element()])),get=id=>nodes.get(id)??null;
get('seed-data').textContent=JSON.stringify(data.paper);
get('community-seed-data').textContent=JSON.stringify(data.empty);
globalThis.document={getElementById:get,createElement:tag=>new Element(tag),documentElement:new Element('html')};
globalThis.location={search:''};
globalThis.window={addEventListener(){}};window.parent=window;
globalThis.AutoRSELeaderboardCore=api;
const pending={};globalThis.fetch=file=>new Promise(resolve=>{pending[file]=resolve;});
const click=id=>get(id).dispatch('click');
const select=cohort=>{get('cohort-select').value=cohort;get('cohort-select').dispatch('change');};
function snapshot(){return {cohort:get('cohort-select').value,caption:get('ranking-caption').textContent,
  headings:get('ranking-head').children[0].children.map(cell=>cell.textContent),
  pressed:[get('view-rankings').attributes['aria-pressed'],get('view-scores').attributes['aria-pressed']],
  rows:get('ranking-rows').children.map(row=>row.children.map(cell=>({text:cell.textContent,colSpan:cell.colSpan,aria:cell.attributes['aria-label']})))};}
'''
            script += self.controls + "\n"
        script += "\n(async()=>{\n" + body + "\n})().catch(error=>{console.error(error.stack);process.exitCode=1;});"
        result = subprocess.run([shutil.which("node"), "-e", script], text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_views_keep_integer_competition_ranks_instead_of_averaging_raw_scores(self):
        result = self.run_node("""
const boards={paper:data.paper,community:data.community};
console.log(JSON.stringify(['rankings','scores'].map(view=>api.presentation(boards,{cohort:'community',view}))));
""")
        expected = [(row["id"], row["overall_rank"], row["mean_task_rank"])
                    for row in community_fixture()["rows"]]
        self.assertEqual([item[0] for item in expected], ["balanced", "tied", "spiky"])
        self.assertEqual([item[1] for item in expected], [1, 1, 3])
        for display in result:
            self.assertEqual([(entry["row"]["id"], entry["rank"], entry["meanRank"])
                              for entry in display["rows"]], expected)
            self.assertTrue(all(type(entry["rank"]) is int for entry in display["rows"]))

    def test_score_view_preserves_all_six_means_deviations_and_trial_counts(self):
        result = self.run_node("""
const boards={paper:data.paper,community:data.community};
console.log(JSON.stringify(['paper','community'].map(cohort=>api.presentation(boards,{cohort,view:'scores'}))));
""")
        for display, source in zip(result, (self.paper, community_fixture())):
            by_id = {row["id"]: row for row in source["rows"]}
            self.assertEqual(display["tasks"], [{"name": task["name"], "metric": task["metric"]}
                                               for task in source["tasks"]])
            for entry in display["rows"]:
                row = by_id[entry["row"]["id"]]
                self.assertEqual(len(entry["scores"]), 6)
                for index, cell in enumerate(entry["scores"]):
                    self.assertEqual(cell, {"task": source["task_order"][index],
                                            "metric": source["tasks"][index]["metric"],
                                            "mean": row["scores"][index], "sd": row["sd"][index],
                                            "trials": row["trial_counts"][index],
                                            "text": f'{four(row["scores"][index])} ± {four(row["sd"][index])}'})
        paper_counts = [cell["trials"] for row in result[0]["rows"] for cell in row["scores"]]
        self.assertEqual(len(paper_counts), 42)
        self.assertEqual(paper_counts.count(2), 1)

    def test_explicit_cohorts_stay_separate_and_empty_community_has_no_paper_fallback(self):
        result = self.run_node("""
const boards={paper:data.paper,community:data.empty};
const empty=api.presentation(boards,{cohort:'community',view:'scores'});
boards.community=data.community;
const paper=api.presentation(boards,{cohort:'paper'}),community=api.presentation(boards,{cohort:'community'});
console.log(JSON.stringify({empty,paper,community,defaultBoard:api.presentation(boards)}));
""")
        self.assertEqual(result["empty"]["rows"], [])
        self.assertEqual(result["empty"]["label"], "Community results")
        self.assertTrue(result["empty"]["emptyMessage"])
        self.assertEqual(len(result["paper"]["rows"]), 7)
        self.assertEqual(result["paper"]["label"], "Paper reference")
        self.assertEqual(len(result["community"]["rows"]), 3)
        self.assertEqual(result["community"]["label"], "Community results")
        self.assertEqual(result["defaultBoard"]["cohort"], "paper")
        self.assertTrue(all(item["row"]["provenance"] == "Reviewed community"
                            for item in result["community"]["rows"]))

    def test_invalid_selections_swapped_cohorts_and_laundered_rows_are_rejected(self):
        result = self.run_node("""
const boards={paper:data.paper,community:data.community};
const clone=()=>JSON.parse(JSON.stringify(boards));
const mixed=clone();mixed.community.rows[0].provenance='Paper reference';
const paperMixed=clone();paperMixed.paper.rows[0].provenance='Reviewed community';
const unlabelled=clone();delete unlabelled.community.rows[0].provenance;
const calls=[()=>api.presentation(boards,{cohort:'all'}),()=>api.presentation(boards,{view:'mean-score'}),
()=>api.presentation({paper:data.community,community:data.paper},{cohort:'paper'}),
()=>api.presentation({paper:data.community,community:data.paper},{cohort:'community'}),
()=>api.presentation(mixed,{cohort:'community'}),()=>api.presentation(paperMixed,{cohort:'paper'}),
()=>api.presentation(unlabelled,{cohort:'community'})];
console.log(JSON.stringify(calls.map(call=>{try{call();return false;}catch{return true;}})));
""")
        self.assertEqual(result, [True] * 7)

    def test_presentation_does_not_mutate_frozen_input_data(self):
        result = self.run_node("""
function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
const boards=freeze({paper:data.paper,community:data.community}),before=JSON.stringify(boards);
for(const cohort of ['community','paper'])for(const view of ['scores','rankings'])api.presentation(boards,{cohort,view});
console.log(JSON.stringify(JSON.stringify(boards)===before));
""")
        self.assertTrue(result)

    def test_real_view_controls_render_six_score_columns_and_integer_rank_cells(self):
        result = self.run_node("""
const rankings=snapshot();click('view-scores');const scores=snapshot();click('view-rankings');
console.log(JSON.stringify({rankings,scores,returned:snapshot()}));
""", browser=True)
        rankings, scores = result["rankings"], result["scores"]
        self.assertEqual(rankings["headings"], ["Model / agent", "Rank"])
        self.assertEqual(rankings["pressed"], ["true", "false"])
        self.assertEqual(scores["pressed"], ["false", "true"])
        self.assertEqual(len(scores["headings"]), 8)
        self.assertEqual(scores["headings"][1:-1],
                         [task["name"] + task["metric"] for task in self.paper["tasks"]])
        self.assertEqual(scores["headings"][-1], "Rank")
        self.assertEqual(result["returned"], rankings)
        for compact, expanded in zip(rankings["rows"], scores["rows"]):
            self.assertEqual(len(compact), 2)
            self.assertEqual(len(expanded), 8)
            self.assertEqual(compact[0], expanded[0])
            self.assertEqual(compact[-1], expanded[-1])
            self.assertRegex(expanded[-1]["text"], r"^[1-9][0-9]*$")
            # Model labels repeat across harnesses; resolve the full visible identity.
            row = next(row for row in self.paper["rows"]
                       if expanded[0]["text"] == row["model"] + row["harness"])
            for index, cell in enumerate(expanded[1:-1]):
                self.assertEqual(cell["text"].replace(" ", ""),
                                 f'{four(row["scores"][index])}±{four(row["sd"][index])}')
                self.assertIn(f'{row["trial_counts"][index]} trials', cell["aria"])

    def test_real_cohort_control_preserves_explicit_selection_during_refresh(self):
        result = self.run_node("""
select('community');const emptyRank=snapshot();click('view-scores');const emptyScores=snapshot();
select('paper');
pending['community-leaderboard.json']({ok:true,status:200,json:async()=>data.community});
pending['leaderboard-data.json']({ok:true,status:200,json:async()=>data.paper});
await new Promise(resolve=>setImmediate(resolve));
const afterRefresh=snapshot();select('community');const communityScores=snapshot();
click('view-rankings');const communityRank=snapshot();select('paper');
console.log(JSON.stringify({emptyRank,emptyScores,afterRefresh,communityScores,communityRank,paper:snapshot()}));
""", browser=True)
        for key, span in (("emptyRank", 2), ("emptyScores", 8)):
            board = result[key]
            self.assertEqual(board["cohort"], "community")
            self.assertIn("Community results", board["caption"])
            self.assertEqual(len(board["rows"]), 1)
            self.assertEqual(board["rows"][0][0]["colSpan"], span)
            self.assertIn("No reviewed community results", board["rows"][0][0]["text"])
        self.assertEqual(result["afterRefresh"]["cohort"], "paper")
        self.assertEqual(len(result["afterRefresh"]["rows"]), 7)
        self.assertIn("Paper reference", result["afterRefresh"]["caption"])
        community = result["communityScores"]
        self.assertEqual(len(community["rows"]), 3)
        self.assertIn("Community results", community["caption"])
        self.assertEqual([row[-1]["text"] for row in community["rows"]], ["1", "1", "3"])
        self.assertEqual([row[0] for row in community["rows"]],
                         [row[0] for row in result["communityRank"]["rows"]])
        self.assertEqual(result["paper"]["cohort"], "paper")
        self.assertEqual(len(result["paper"]["rows"]), 7)


if __name__ == "__main__":
    unittest.main()
