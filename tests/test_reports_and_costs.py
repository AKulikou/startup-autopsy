from datetime import datetime

import pytest
from conftest import lens_result, synthesis_result

from core import token_summary
from core.report_builder import build_report
from core.result_writer import ResultWriter, lens_report_path
from evaluators.schemas import codes_as_words, confidence_label, verdict_label, verdict_meaning
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


def test_report_shows_what_holds_up_with_its_lenses():
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(), [])
    assert "## What Holds Up\n\n- The problem is real for freelancers. *(Reality Auditor)*" in report


def test_empty_what_holds_up_is_said_plainly_not_left_blank():
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(what_holds_up=[]), [])
    assert "## What Holds Up\n\nThe lenses found nothing" in report


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


def test_report_lists_lenses_skipped_by_the_input_check():
    skipped = [{"lens": "Viral Product Designer", "reason": "A local bakery has no network effect."}]
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(), [lens_row("Reality Auditor")],
                          skipped_lenses=skipped)
    assert "- **Viral Product Designer:** A local bakery has no network effect." in report
    assert "Not run" not in build_report("idea", datetime(2026, 9, 25), synthesis_row(), [])


def test_runs_started_in_the_same_second_get_separate_directories(tmp_path):
    writer = ResultWriter(str(tmp_path))
    started = datetime(2026, 9, 27, 12, 0, 0)
    first, second = writer.create_run_dir("meals", started), writer.create_run_dir("meals", started)
    assert first.name == "2026-09-27_12-00-00_meals"
    assert second.name == "2026-09-27_12-00-00_meals_2"


def test_a_lens_warning_shows_in_both_reports(tmp_path):
    warned = {**lens_row("Reality Auditor"), "tokens_used": 1, "input_tokens": 1, "output_tokens": 0,
              "warnings": ["says it searched the web but made no search"]}
    report = build_report("idea", datetime(2026, 9, 25), synthesis_row(), [warned, lens_row("Launch Expert")])
    assert "> **Warning:** Reality Auditor says it searched the web but made no search." in report
    assert report.count("**Warning:**") == 1

    writer = ResultWriter(str(tmp_path))
    started = datetime(2026, 9, 25)
    path = writer.save_result(writer.create_run_dir("idea", started), "idea", started, warned)
    lens_report = path.read_text(encoding="utf-8")
    assert "> **Warning:** this lens says it searched the web but made no search." in lens_report


# Seen in every real report checked on 2026-10-16, despite the prompts asking for words.
REASONING_WITH_CODES = (
    "This is not a NOT_VIABLE situation. The appropriate verdict is NEEDS_VALIDATION rather "
    "than VIABLE_IF. RISKY would imply a blocker. No-Code Stack Master gave a HIGH confidence "
    "VIABLE verdict. I'd place confidence at MEDIUM because demand is untested. "
)


def test_codes_in_the_models_text_become_words():
    assert codes_as_words(REASONING_WITH_CODES) == (
        "This is not a 'not viable' situation. The appropriate verdict is 'needs validation' rather "
        "than 'viable if conditions hold'. 'Risky' would imply a blocker. No-Code Stack Master gave a "
        "high confidence 'viable' verdict. I'd place confidence at medium because demand is untested. "
    )
    assert codes_as_words("- `VIABLE_IF` holds") == "- 'Viable if conditions hold' holds"
    # Capitals far from the word 'confidence' are left alone.
    assert codes_as_words("Rent is LOW in the suburbs.") == "Rent is LOW in the suburbs."


def test_both_reports_show_codes_from_the_models_text_as_words(tmp_path):
    synthesis = synthesis_row(reasoning=REASONING_WITH_CODES * 2,
                              summary="Needs validation, not NOT_VIABLE: demand is untested so far.")
    lens = {**lens_row("Reality Auditor", summary="A HIGH confidence VIABLE verdict within this lens."),
            "tokens_used": 1, "input_tokens": 1, "output_tokens": 0}
    started = datetime(2026, 9, 25)
    report = build_report("idea", started, synthesis, [lens])
    writer = ResultWriter(str(tmp_path))
    path = writer.save_result(writer.create_run_dir("idea", started), "idea", started, lens)
    lens_report = path.read_text(encoding="utf-8")
    for text in (report, lens_report):
        assert not any(code in text for code in ("NOT_VIABLE", "VIABLE_IF", "NEEDS_VALIDATION", "VIABLE "))
    assert "'needs validation' rather than 'viable if conditions hold'" in report
    assert "A high confidence 'viable' verdict" in lens_report
