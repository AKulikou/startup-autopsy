"""The eval's own grading and summary logic: who tests the grader."""

import json

import pytest

from eval import run_eval
from eval.grading import (
    calibration,
    constant_baselines,
    grade_gate,
    grade_pipeline,
    lens_flip_rates,
    stability,
    wilson,
)


def row(case, rep, verdict, confidence="MEDIUM", expected=("RISKY",), lenses=None):
    return {"prompt_id": case, "rep": rep,
            "grade": {"in_range": int(verdict in expected)},
            "meta": {"verdict": verdict, "confidence": confidence, "expected": list(expected),
                     "lens_verdicts": lenses or {}}}


# --- one attempt -----------------------------------------------------------

@pytest.mark.parametrize("decision, expected, injection, grade", [
    # grade = (correct, false_reject, false_accept, injection_ok)
    ("ANALYZABLE", ["ANALYZABLE"], False, (1, 0, 0, 1)),
    ("TOO_VAGUE", ["ANALYZABLE"], False, (0, 1, 0, 1)),
    ("ANALYZABLE", ["NOT_AN_IDEA"], False, (0, 0, 1, 1)),
    ("TOO_SHORT", ["TOO_SHORT"], True, (1, 0, 0, 0)),
])
def test_gate_grade(decision, expected, injection, grade):
    keys = ("correct", "false_reject", "false_accept", "injection_ok")
    assert grade_gate(decision, injection, expected) == dict(zip(keys, grade, strict=True))


def test_gate_grade_expects_the_injection_flag_when_the_case_says_so():
    assert grade_gate("ANALYZABLE", True, ["ANALYZABLE"], expect_injection=True)["injection_ok"] == 1
    assert grade_gate("ANALYZABLE", False, ["ANALYZABLE"], expect_injection=True)["injection_ok"] == 0


def test_pipeline_grade():
    assert grade_pipeline("RISKY", ["RISKY", "NOT_VIABLE"], [], ["success"] * 6) == \
        {"in_range": 1, "consistent": 1, "all_lenses_ok": 1}
    assert grade_pipeline("VIABLE", ["RISKY"], ["positive although a lens said not viable"],
                          ["success", "error"]) == {"in_range": 0, "consistent": 0, "all_lenses_ok": 0}


def test_wilson_interval_matches_the_published_baseline():
    lo, hi = wilson(29, 34)
    assert round(lo, 2) == 0.70 and round(hi, 2) == 0.94
    assert wilson(0, 0) == (0.0, 0.0)
    assert wilson(5, 5)[1] == 1.0


# --- reference baselines ---------------------------------------------------

def test_constant_baselines_count_what_trivial_answers_would_score():
    base = constant_baselines([["RISKY", "NOT_VIABLE"], ["RISKY"], ["VIABLE", "VIABLE_IF"]])
    assert base["n"] == 3
    assert base["always"]["RISKY"] == 2
    assert base["always"]["VIABLE"] == 1
    assert base["always"]["NEEDS_VALIDATION"] == 0
    assert base["random"] == pytest.approx((2 + 1 + 2) / 5)


# --- stability -------------------------------------------------------------

def test_stability_separates_neighbour_changes_from_cross_side_flips():
    rows = [
        row("stable", 0, "RISKY"), row("stable", 1, "RISKY"),
        row("neighbour", 0, "RISKY"), row("neighbour", 1, "NEEDS_VALIDATION"),
        row("flip", 0, "NOT_VIABLE"), row("flip", 1, "VIABLE_IF"),
        row("single_rep", 0, "VIABLE"),
    ]
    stab = stability(rows)
    assert stab["cases"] == 3  # a case with one rep says nothing about stability
    assert stab["changed_cases"] == ["flip", "neighbour"]
    assert stab["cross_side_cases"] == ["flip"]
    assert stab["modal_agreement"] == pytest.approx(4 / 6)
    assert stab["mean_ordinal_spread"] == pytest.approx((0 + 1 + 3) / 3)


def test_modal_agreement_over_more_than_two_reps():
    verdicts = ["RISKY", "RISKY", "RISKY", "NEEDS_VALIDATION", "RISKY"]
    rows = [row("c", i, v) for i, v in enumerate(verdicts)]
    assert stability(rows)["modal_agreement"] == pytest.approx(4 / 5)


def test_calibration_counts_right_and_unanimous_attempts_per_level():
    rows = [
        row("a", 0, "RISKY", "HIGH"), row("a", 1, "RISKY", "HIGH"),
        row("b", 0, "RISKY", "HIGH"), row("b", 1, "NOT_VIABLE", "HIGH"),
        row("c", 0, "VIABLE", "LOW"),
    ]
    cal = calibration(rows)
    assert cal["HIGH"] == {"n": 4, "in_range": 3, "comparable": 4, "all_reps_agree": 2}
    assert cal["LOW"] == {"n": 1, "in_range": 0, "comparable": 0, "all_reps_agree": 0}
    assert "MEDIUM" not in cal


def test_lens_flip_rates_only_compare_lenses_present_in_every_rep():
    rows = [
        row("a", 0, "RISKY", lenses={"Launch": "RISKY", "Legal": "RISKY"}),
        row("a", 1, "RISKY", lenses={"Launch": "VIABLE_IF"}),
        row("b", 0, "RISKY", lenses={"Launch": "RISKY"}),
        row("b", 1, "RISKY", lenses={"Launch": "RISKY"}),
    ]
    assert lens_flip_rates(rows) == {"Launch": (1, 2)}


# --- the printed summary -----------------------------------------------------

def test_summary_shows_the_constant_floor_and_stability(tmp_path, capsys):
    rows = [row("a", 0, "RISKY"), row("a", 1, "NEEDS_VALIDATION"),
            row("b", 0, "RISKY"), row("b", 1, "RISKY")]
    for r in rows:
        r["grade"].update({"consistent": 1, "all_lenses_ok": 1})
        r["cost_usd"] = 0.2
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    run_eval.summarize("pipeline", tmp_path)
    out = capsys.readouterr().out
    assert "always RISKY      4/4 = 100%" in out
    assert "verdict changed   1/2 cases: a" in out
    assert "cross-side flips  0/2" in out
    assert "cost          $0.80" in out


# --- synthesis replay --------------------------------------------------------

def test_a_pipeline_trace_replays_the_synthesis_on_the_same_inputs(fake_claude):
    from eval.replay_synthesis import load_inputs, replay_row
    from synthesis.schemas import SynthesisResult

    case = {"id": "meals", "text": "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week.",
            "expected": ["NEEDS_VALIDATION"]}
    _, trace, extra = run_eval.run_pipeline_case(case)
    inputs = load_inputs(json.loads(json.dumps(trace)))
    assert inputs["original_verdict"] == extra["meta"]["verdict"]
    assert all("analysis" in lens for lens in inputs["lenses"])

    row = replay_row("meals", 0, inputs, case["expected"])
    assert row["status"] == "success" and row["grade"]["in_range"] == 1
    # The replayed synthesis saw the same lens analyses as the original one.
    prompts = [r["messages"][0]["content"] for r in fake_claude.requests
               if r["output_format"] is SynthesisResult]
    assert len(prompts) == 2 and prompts[0] == prompts[1]


def test_a_trace_without_lens_analysis_is_refused():
    from eval.replay_synthesis import TraceError, load_inputs

    lens = {"evaluator_display": "Launch Expert", "status": "success", "verdict": "RISKY"}
    trace = [{"role": "user", "content": "idea"}, {"role": "tool_result", "content": json.dumps(lens)},
             {"role": "assistant", "content": json.dumps({"verdict": "RISKY", "confidence": "LOW"})}]
    with pytest.raises(TraceError, match="predates full lens results"):
        load_inputs(trace)
