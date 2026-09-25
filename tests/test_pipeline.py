"""The whole analysis through AnalysisRunner.analyze(), with a fake Claude."""

import re
import time

from conftest import gate_result, lens_result, response

from config import ENABLED_LENSES
from core.analysis_runner import AnalysisRunner
from evaluators.lenses import select_lenses
from evaluators.schemas import EvaluatorResult
from gate.lens_fit import LensFitResult
from gate.schemas import GateResult
from synthesis.schemas import SynthesisResult

LENS_NAMES = [lens.name for lens in select_lenses(ENABLED_LENSES)]


def analyze(confirm=None):
    return AnalysisRunner(processor=None, confirm_vague_idea=confirm).analyze(
        "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week."
    )


def test_analyzable_idea_runs_every_lens_and_the_synthesis(fake_claude):
    analysis = analyze()
    assert analysis["analyzed"]
    assert len(fake_claude.calls(EvaluatorResult)) == len(LENS_NAMES)
    assert analysis["synthesis"]["verdict"] == "NEEDS_VALIDATION"


def test_not_an_idea_stops_before_any_lens(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("NOT_AN_IDEA"))
    analysis = analyze()
    assert not analysis["analyzed"]
    assert fake_claude.calls(EvaluatorResult) == []


def test_too_vague_stops_unless_the_user_confirms(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    assert not analyze()["analyzed"]
    assert not analyze(confirm=lambda gate: False)["analyzed"]
    assert fake_claude.calls(EvaluatorResult) == []


def test_confirmed_vague_idea_carries_a_note_to_lenses_and_synthesis(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    analysis = analyze(confirm=lambda gate: True)
    assert analysis["analyzed"] and "too vague" in analysis["input_note"]
    for request in fake_claude.calls(EvaluatorResult) + fake_claude.calls(SynthesisResult):
        assert "<input_check>" in request["messages"][0]["content"]


def test_suspected_injection_is_noted_but_does_not_stop_the_analysis(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result(injection_suspected=True))
    analysis = analyze()
    assert analysis["analyzed"]
    assert "instructions addressed to an AI" in analysis["input_note"]


def test_failed_input_check_does_not_block_the_analysis(fake_claude):
    def fail(kwargs):
        raise ConnectionError("Connection error.")
    fake_claude.handlers[GateResult] = fail
    assert analyze()["analyzed"]


def test_lenses_run_in_parallel_and_reach_the_synthesis_in_config_order(fake_claude):
    # Earlier lenses finish later, so completion order is the reverse of config order.
    delays = {name: 0.05 * (len(LENS_NAMES) - i) for i, name in enumerate(LENS_NAMES)}

    def slow_lens(kwargs):
        lens = next(lens for lens in select_lenses(ENABLED_LENSES) if lens.role in kwargs["system"])
        time.sleep(delays[lens.name])
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = slow_lens
    started = time.monotonic()
    analysis = analyze()
    elapsed = time.monotonic() - started

    assert elapsed < sum(delays.values()) * 0.8  # parallel, not sequential
    synthesis_prompt = fake_claude.calls(SynthesisResult)[0]["messages"][0]["content"]
    order = re.findall(r'<lens name="([^"]+)"', synthesis_prompt)
    assert order == LENS_NAMES
    assert [r["evaluator_display"] for r in analysis["lenses"]] == LENS_NAMES


def test_one_failed_lens_does_not_stop_the_others_or_the_synthesis(fake_claude):
    first_role = select_lenses(ENABLED_LENSES)[0].role

    def one_fails(kwargs):
        if first_role in kwargs["system"]:
            raise ConnectionError("Connection error.")
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = one_fails
    analysis = analyze()
    statuses = [r["status"] for r in analysis["lenses"]]
    assert statuses.count("error") == 1
    assert analysis["synthesis"]["status"] == "success"
    assert f"{len(LENS_NAMES) - 1} of {len(LENS_NAMES)} lenses succeeded" in \
        fake_claude.calls(SynthesisResult)[0]["messages"][0]["content"]


def test_lens_prompt_wraps_the_idea_and_treats_its_claims_as_unverified(fake_claude):
    analyze()
    request = fake_claude.calls(EvaluatorResult)[0]
    assert "<business_idea>" in request["messages"][0]["content"]
    assert "unverified" in request["system"]
    assert "single quotes" in request["system"]



def enable_lens_selection(monkeypatch):
    import core.analysis_runner as runner_module
    monkeypatch.setattr(runner_module, "LENS_SELECTION", True)
    return [lens for lens in select_lenses(ENABLED_LENSES) if lens.applies_to]


def fits(candidates, misfit_key=None):
    return LensFitResult(lens_fit=[
        {"lens": lens.key, "applies": lens.key != misfit_key, "reason": "A reason for this."}
        for lens in candidates
    ])


def test_without_lens_selection_there_is_no_lens_fit_call(fake_claude):
    analysis = analyze()
    assert fake_claude.calls(LensFitResult) == [] and analysis["skipped_lenses"] == []


def test_lens_selection_skips_a_lens_that_does_not_fit(fake_claude, monkeypatch):
    candidates = enable_lens_selection(monkeypatch)
    misfit = candidates[0]
    fake_claude.handlers[LensFitResult] = lambda kw: response(fits(candidates, misfit.key))
    analysis = analyze()

    fit_prompt = fake_claude.calls(LensFitResult)[0]["messages"][0]["content"]
    assert all(f"- {lens.key}:" in fit_prompt for lens in candidates)
    assert "<candidate" not in fake_claude.calls(GateResult)[0]["messages"][0]["content"]
    assert len(fake_claude.calls(EvaluatorResult)) == len(LENS_NAMES) - 1
    assert misfit.name not in [r["evaluator_display"] for r in analysis["lenses"]]
    assert analysis["skipped_lenses"] == [{"lens": misfit.name, "reason": "A reason for this."}]


def test_lens_fit_answer_missing_a_candidate_is_retried(fake_claude, monkeypatch):
    candidates = enable_lens_selection(monkeypatch)
    answers = [LensFitResult(lens_fit=fits(candidates).lens_fit[1:]), fits(candidates)]
    fake_claude.handlers[LensFitResult] = lambda kw: response(answers.pop(0))
    analyze()
    assert len(fake_claude.calls(LensFitResult)) == 2


def test_failed_lens_fit_runs_every_lens(fake_claude, monkeypatch):
    enable_lens_selection(monkeypatch)

    def fail(kw):
        raise RuntimeError("API down")
    fake_claude.handlers[LensFitResult] = fail
    analysis = analyze()
    assert len(fake_claude.calls(EvaluatorResult)) == len(LENS_NAMES)
    assert analysis["lens_fit"]["status"] == "error" and analysis["skipped_lenses"] == []
