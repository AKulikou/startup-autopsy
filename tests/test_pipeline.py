"""The whole analysis through AnalysisRunner.analyze(), with a fake Claude."""

import re
import time

from config import ENABLED_LENSES
from core.analysis_runner import AnalysisRunner
from evaluators.lenses import select_lenses
from evaluators.schemas import EvaluatorResult
from gate.schemas import GateResult
from synthesis.schemas import SynthesisResult

from conftest import gate_result, lens_result, response

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
        lens = next(l for l in select_lenses(ENABLED_LENSES) if l.role in kwargs["system"])
        time.sleep(delays[lens.name])
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = slow_lens
    started = time.monotonic()
    analysis = analyze()
    elapsed = time.monotonic() - started

    assert elapsed < sum(delays.values()) * 0.8  # parallel, not sequential
    order = re.findall(r'<lens name="([^"]+)"', fake_claude.calls(SynthesisResult)[0]["messages"][0]["content"])
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
