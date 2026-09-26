"""report.json: the analysis as structured data next to report.md."""

import json

from conftest import lens_result, response

from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor
from evaluators.schemas import EvaluatorResult

IDEA = "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week, ordered online."


def run_and_load(tmp_path) -> dict:
    ideas = tmp_path / "ideas"
    ideas.mkdir()
    (ideas / "meals.txt").write_text(IDEA, encoding="utf-8")
    results = tmp_path / "results"
    AnalysisRunner(IdeaProcessor(ideas_dir=str(ideas), results_dir=str(results))).run("meals")
    run_dir = next(results.iterdir())
    assert (run_dir / "report.md").exists()
    return json.loads((run_dir / "report.json").read_text(encoding="utf-8"))


def test_report_json_holds_the_synthesis_and_every_lens_with_codes(fake_claude, tmp_path):
    document = run_and_load(tmp_path)
    assert document["format_version"] == 1
    assert document["idea_name"] == "meals"
    assert document["input_check"]["decision"] == "ANALYZABLE"
    assert document["synthesis"]["verdict"] == "NEEDS_VALIDATION"
    assert document["synthesis"]["what_holds_up"]
    assert len(document["lenses"]) == len(fake_claude.calls(EvaluatorResult))
    assert all(lens["verdict"] == "NEEDS_VALIDATION" for lens in document["lenses"])


def test_a_failed_lens_stays_in_report_json_with_its_error(fake_claude, tmp_path):
    calls = {"n": 0}

    def one_fails(kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("down")
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = one_fails
    document = run_and_load(tmp_path)
    failed = [lens for lens in document["lenses"] if lens["status"] == "error"]
    assert len(failed) == 1
    assert "down" in failed[0]["error"]
    assert "verdict" not in failed[0]
