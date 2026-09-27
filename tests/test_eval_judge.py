"""The must_find / must_not judge of the eval, with the fake client."""

import pytest
from conftest import judge_answer, response, synthesis_result

from eval import run_eval
from eval.judge import JudgeResult, StatementCheck, judge_report, judge_user_prompt, report_text

CASE = {"id": "arith", "primary": "RISKY", "acceptable": [],
        "must_find": ["200 x 30 EUR is 6,000 EUR per month, not 60,000"],
        "must_not": ["Accepts 60,000 EUR per month as correct"]}


def synthesis() -> dict:
    return synthesis_result().model_dump(mode="json")


def test_a_case_without_statements_is_not_judged(fake_claude):
    assert judge_report({"id": "x", "primary": "RISKY"}, synthesis()) == {"status": "skipped"}
    assert fake_claude.calls(JudgeResult) == []


def test_the_prompt_lists_numbered_statements_with_their_kind():
    prompt = judge_user_prompt(CASE, synthesis())
    assert "1. [must_find] 200 x 30 EUR is 6,000 EUR per month, not 60,000" in prompt
    assert "2. [must_not] Accepts 60,000 EUR per month as correct" in prompt
    assert "<report>" in prompt and "Deciding factors:" in prompt


def test_flaw_found_and_forbidden_statement_are_graded_separately(fake_claude):
    def answer(kwargs):
        return response(JudgeResult(checks=[
            StatementCheck(index=1, kind="must_find", present=True, evidence="'only 6,000 EUR'"),
            StatementCheck(index=2, kind="must_not", present=False, evidence="none"),
        ]))
    fake_claude.handlers[JudgeResult] = answer
    result = judge_report(CASE, synthesis())
    assert result["status"] == "success"
    assert result["flaw_found"] == 1 and result["must_not_ok"] == 1
    assert result["checks"][0]["statement"] == CASE["must_find"][0]
    assert fake_claude.calls(JudgeResult)[0]["model"] == "claude-haiku-4-5"


def test_a_missed_flaw_and_a_forbidden_statement_fail(fake_claude):
    fake_claude.handlers[JudgeResult] = lambda kwargs: judge_answer(kwargs, present=True)
    result = judge_report(CASE, synthesis())
    assert result["flaw_found"] == 1 and result["must_not_ok"] == 0
    fake_claude.handlers[JudgeResult] = lambda kwargs: judge_answer(kwargs, present=False)
    result = judge_report(CASE, synthesis())
    assert result["flaw_found"] == 0 and result["must_not_ok"] == 1


def test_an_answer_that_skips_a_statement_is_retried_then_reported_as_error(fake_claude):
    fake_claude.handlers[JudgeResult] = lambda kwargs: response(JudgeResult(checks=[
        StatementCheck(index=1, kind="must_find", present=True, evidence="'quote'")]))
    result = judge_report(CASE, synthesis())
    assert result["status"] == "error" and "expected 1..2" in result["error"]
    assert len(fake_claude.calls(JudgeResult)) == 2  # one retry
    assert "flaw_found" not in result  # never guessed


def test_report_text_includes_what_the_founder_reads():
    text = report_text(synthesis())
    for part in ("Verdict:", "Summary:", "Killer risks:", "Conflicts:", "Next steps:"):
        assert part in text


def test_pipeline_eval_adds_judge_metrics_only_for_cases_with_statements(fake_claude):
    fake_claude.handlers[JudgeResult] = lambda kwargs: judge_answer(kwargs, present=True)
    case = {**CASE, "text": "Online booking for physiotherapists in Poland, 30 EUR a month.",
            "primary": "NEEDS_VALIDATION"}
    grade, _, extra = run_eval.run_pipeline_case(case)
    assert grade["flaw_found"] == 1 and grade["must_not_ok"] == 0
    assert extra["meta"]["judge"]["status"] == "success"
    assert extra["meta"]["judge_cost_usd"] == pytest.approx((1000 * 1 + 500 * 5) / 1e6)

    plain = {"id": "plain", "text": case["text"], "primary": "NEEDS_VALIDATION"}
    grade, _, extra = run_eval.run_pipeline_case(plain)
    assert "flaw_found" not in grade and extra["meta"]["judge"] == {"status": "skipped"}
