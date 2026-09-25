from datetime import datetime

import pytest
from conftest import lens_result, synthesis_result

from core import token_summary
from core.report_builder import build_report
from core.result_writer import lens_report_path
from evaluators.schemas import confidence_label, verdict_label, verdict_meaning
from gate.schemas import gate_decision_label
from synthesis.synthesizer import consistency_warnings


def lens_row(name, **overrides):
    return {"evaluator_display": name, "status": "success",
            **lens_result(**overrides).model_dump(mode="json")}


def synthesis_row(**overrides):
    return {"evaluator_display": "Synthesis", "status": "success",
            **synthesis_result(**overrides).model_dump(mode="json")}


def test_codes_render_as_plain_words():
    assert verdict_label("VIABLE_IF") == "Viable if conditions hold"
    assert verdict_meaning("NOT_VIABLE").startswith("a fundamental flaw")
    assert confidence_label("HIGH") == "High"
    assert gate_decision_label("NOT_AN_IDEA") == "not a business idea"


def test_lens_report_path_keeps_word_boundaries():
    assert lens_report_path("No-Code Stack Master") == "lenses/no_code_stack_master.md"


def test_report_shows_the_verdict_in_words_and_links_the_lenses():
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(), [lens_row("Reality Auditor")])
    assert "## Verdict: Needs validation" in report
    assert "NEEDS_VALIDATION" not in report
    assert "(lenses/reality_auditor.md)" in report


def test_failed_synthesis_gives_no_verdict_instead_of_an_invented_one():
    failed = {"evaluator_display": "Synthesis", "status": "error", "error": "APIConnectionError: down"}
    report = build_report("idea", datetime(2026, 9, 25), failed, [lens_row("Reality Auditor")])
    assert "## No Overall Verdict" in report
    assert "## Verdict:" not in report


def test_input_check_note_appears_in_the_report_header():
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(), [], input_note="Too vague.")
    assert "> **Input check:** Too vague." in report.split("## Verdict")[0]


def test_consistency_warnings():
    not_viable_lens = [lens_row("Reality Auditor", verdict="NOT_VIABLE")]
    assert consistency_warnings(synthesis_row(verdict="VIABLE_IF"), not_viable_lens)
    assert consistency_warnings(synthesis_row(verdict="NOT_VIABLE", next_steps=["Interview users."]), [])
    assert consistency_warnings(
        synthesis_row(verdict="NOT_VIABLE", next_steps=["Do not pursue: illegal."]), not_viable_lens) == []


def test_cost_uses_separate_input_and_output_prices(monkeypatch):
    monkeypatch.setattr(token_summary, "MODEL", "claude-sonnet-4-6")
    # A real three-lens run: 4,792 input and 8,309 output tokens.
    assert token_summary.estimate_cost(4792, 8309) == pytest.approx(0.139011)


def test_unknown_model_has_no_invented_cost(monkeypatch):
    monkeypatch.setattr(token_summary, "MODEL", "some-unknown-model")
    assert token_summary.estimate_cost(1000, 1000) is None
    assert token_summary.format_cost(None) == "cost n/a"


def test_each_call_is_priced_with_its_own_model(monkeypatch, caplog):
    monkeypatch.setattr(token_summary, "MODEL", "claude-sonnet-4-6")
    calls = [
        {"evaluator_display": "Lens", "input_tokens": 1_000_000, "output_tokens": 0},
        {"evaluator_display": "Translation", "model": "claude-haiku-4-5",
         "input_tokens": 0, "output_tokens": 1_000_000},
    ]
    with caplog.at_level("INFO"):
        token_summary.log_token_summary(calls)
    # 1M Sonnet input tokens at $3 plus 1M Haiku output tokens at $5.
    assert "est. cost $8.0000 (claude-haiku-4-5, claude-sonnet-4-6)" in caplog.text
