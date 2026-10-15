"""Progress events of AnalysisRunner (the web UI's live view), with a fake Claude."""

import pytest
from conftest import gate_result, lens_result, response

from config import ENABLED_LENSES
from core.analysis_runner import AnalysisRunner
from core.progress import ProgressEvent
from evaluators.lenses import select_lenses
from evaluators.schemas import EvaluatorResult
from gate.schemas import GateResult

IDEA = "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week."
LENSES = select_lenses(ENABLED_LENSES)


def analyze(confirm=None):
    events = []
    analysis = AnalysisRunner(processor=None, confirm_vague_idea=confirm,
                              on_progress=events.append).analyze(IDEA)
    return analysis, events


def steps(events, stage=None):
    return [(e.stage, e.status) for e in events if stage is None or e.stage == stage]


def test_a_full_run_reports_every_stage_in_order(fake_claude):
    analysis, events = analyze()
    assert analysis["analyzed"]
    assert steps(events)[:2] == [("input_check", "started"), ("input_check", "done")]
    lens_steps = steps(events, "lens")
    assert lens_steps.count(("lens", "started")) == len(LENSES)
    assert lens_steps.count(("lens", "done")) == len(LENSES)
    # Every lens has started before the first one reports back.
    assert lens_steps[:len(LENSES)] == [("lens", "started")] * len(LENSES)
    assert steps(events)[-2:] == [("synthesis", "started"), ("synthesis", "done")]


def test_events_carry_words_for_people_and_codes_only_for_styling(fake_claude):
    _, events = analyze()
    gate_done = events[1]
    assert gate_done.text == "idea accepted for analysis"
    started = [e for e in events if e.stage == "lens" and e.status == "started"]
    expected = [(lens.key, lens.name, lens.focus) for lens in LENSES]
    assert [(e.key, e.label, e.text) for e in started] == expected
    lens_done = next(e for e in events if e.stage == "lens" and e.status == "done")
    assert (lens_done.verdict, lens_done.verdict_text, lens_done.confidence_text) == \
        ("NEEDS_VALIDATION", "Needs validation", "Medium")
    assert lens_done.text == lens_result().summary
    synthesis_done = events[-1]
    assert synthesis_done.verdict_text == "Needs validation"


def test_every_billed_call_reports_its_cost(fake_claude):
    _, events = analyze()
    billed = [e for e in events if e.status == "done"]
    assert billed and all(e.cost_usd and e.cost_usd > 0 for e in billed)
    assert all(e.cost_usd is None for e in events if e.status == "started")


def test_a_failed_lens_is_reported_and_the_synthesis_still_runs(fake_claude):
    first = LENSES[0]

    def one_fails(kwargs):
        if first.role in kwargs["system"]:
            raise ConnectionError("Connection error.")
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = one_fails
    _, events = analyze()
    failed = [e for e in events if e.stage == "lens" and e.status == "failed"]
    assert [(e.key, e.label) for e in failed] == [(first.key, first.name)]
    assert "Connection error" in failed[0].text
    assert ("synthesis", "done") in steps(events)


def test_no_successful_lens_means_the_synthesis_is_skipped(fake_claude):
    def all_fail(kwargs):
        raise ConnectionError("Connection error.")

    fake_claude.handlers[EvaluatorResult] = all_fail
    _, events = analyze()
    assert steps(events, "synthesis") == [("synthesis", "skipped")]
    assert "no lens succeeded" in events[-1].text


def test_a_vague_idea_stops_after_the_input_check(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    analysis, events = analyze()
    assert not analysis["analyzed"]
    assert steps(events) == [("input_check", "started"), ("input_check", "done")]
    assert events[-1].text == "too vague to analyze"


def test_a_failed_input_check_is_reported_and_the_analysis_goes_on(fake_claude):
    def gate_fails(kwargs):
        raise ConnectionError("Connection error.")

    fake_claude.handlers[GateResult] = gate_fails
    analysis, events = analyze()
    assert analysis["analyzed"]
    assert steps(events)[1] == ("input_check", "failed")
    assert "continuing without the input check" in events[1].text


def test_a_failing_callback_never_stops_a_paid_run(fake_claude):
    def broken(event):
        raise RuntimeError("the page went away")

    analysis = AnalysisRunner(processor=None, on_progress=broken).analyze(IDEA)
    assert analysis["analyzed"]
    assert analysis["synthesis"]["status"] == "success"


def test_an_event_with_an_unknown_status_is_refused():
    with pytest.raises(ValueError):
        ProgressEvent("lens", "finished")
