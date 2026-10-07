"""Optional web search for the fact-heavy lenses (WEB_SEARCH=on)."""

import pytest
from conftest import lens_result, response

from core.token_summary import call_cost
from evaluators import evaluator as evaluator_module
from evaluators.evaluator import WEB_SEARCH_GUIDANCE, Evaluator
from evaluators.lenses import select_lenses
from evaluators.schemas import EvaluatorResult

IDEA = "Garden tool rental for dacha owners near Minsk, 15 BYN a day plus 10 BYN delivery."


def lens(key):
    return select_lenses((key,))[0]


def test_without_the_switch_no_lens_gets_the_search_tool(fake_claude):
    Evaluator(lens("reality_auditor"), IDEA).evaluate()
    request = fake_claude.calls(EvaluatorResult)[0]
    assert "tools" not in request
    assert WEB_SEARCH_GUIDANCE not in request["system"]


@pytest.fixture
def search_on(monkeypatch):
    monkeypatch.setattr(evaluator_module, "WEB_SEARCH", True)


def test_only_the_listed_lenses_search(fake_claude, search_on):
    Evaluator(lens("reality_auditor"), IDEA).evaluate()
    Evaluator(lens("no_code_stack"), IDEA).evaluate()
    auditor, no_code = fake_claude.calls(EvaluatorResult)
    assert auditor["tools"][0]["type"].startswith("web_search")
    assert WEB_SEARCH_GUIDANCE in auditor["system"]
    assert "tools" not in no_code


def test_a_paused_search_turn_is_resumed_and_every_part_is_billed(fake_claude, search_on):
    answers = iter([
        response(None, stop_reason="pause_turn", input_tokens=20000, output_tokens=100, web_searches=2),
        response(lens_result(), input_tokens=25000, output_tokens=2000, web_searches=1),
    ])
    fake_claude.handlers[EvaluatorResult] = lambda kwargs: next(answers)
    result = Evaluator(lens("reality_auditor"), IDEA).evaluate()

    first, second = fake_claude.calls(EvaluatorResult)
    assert len(first["messages"]) == 1
    # The resumed request repeats the question and the paused turn, with no new user message.
    assert [m["role"] for m in second["messages"]] == ["user", "assistant"]
    assert result["status"] == "success"
    assert (result["input_tokens"], result["output_tokens"], result["web_searches"]) == (45000, 2100, 3)


def test_a_turn_that_never_resumes_is_an_error_not_a_hang(fake_claude, search_on):
    fake_claude.handlers[EvaluatorResult] = lambda kwargs: response(None, stop_reason="pause_turn")
    result = Evaluator(lens("reality_auditor"), IDEA).evaluate()
    assert result["status"] == "error"
    assert "still paused" in result["error"]


def test_searches_are_priced_on_top_of_tokens(monkeypatch):
    monkeypatch.setattr("core.token_summary.MODEL", "claude-sonnet-4-6")
    without = call_cost({"input_tokens": 1_000_000, "output_tokens": 0})
    with_searches = call_cost({"input_tokens": 1_000_000, "output_tokens": 0, "web_searches": 3})
    assert with_searches == pytest.approx(without + 0.03)


def test_effort_is_sent_only_when_set(fake_claude, monkeypatch):
    Evaluator(lens("reality_auditor"), IDEA).evaluate()
    monkeypatch.setattr(evaluator_module, "ANALYSIS_EFFORT", "low")
    Evaluator(lens("reality_auditor"), IDEA).evaluate()
    default, low = fake_claude.calls(EvaluatorResult)
    assert "output_config" not in default
    assert low["output_config"] == {"effort": "low"}


SEEN_CLAIMS = [
    "I searched for current platform eligibility policies.",
    "**Verified current platforms (searched May 2026):**",
    "On Code4rena status: search results suggest a restructuring.",
    "### AI Risk Assessment\n\nSearched for current state of AI in smart-contract auditing.",
]


@pytest.mark.parametrize("claim", SEEN_CLAIMS)
def test_a_search_claim_without_a_search_is_found(claim):
    result = {**lens_result(analysis="A long analysis. " * 50 + claim).model_dump(), "web_searches": 0}
    assert evaluator_module.unbacked_search_claim(result)


def test_a_search_claim_backed_by_a_search_is_fine():
    result = {**lens_result(analysis=SEEN_CLAIMS[0] * 40).model_dump(), "web_searches": 2}
    assert evaluator_module.unbacked_search_claim(result) is None


@pytest.mark.parametrize("text", [
    "The founder searched for a niche and found none.",
    "Customers rarely search for this; research suggests low demand.",
])
def test_other_mentions_of_searching_are_not_claims(text):
    result = {**lens_result(analysis=text * 40).model_dump(), "web_searches": 0}
    assert evaluator_module.unbacked_search_claim(result) is None


def test_an_unbacked_search_claim_is_kept_as_a_warning_in_the_result(fake_claude, search_on):
    claim = lens_result(analysis="A thorough lens analysis. " * 80 + "I searched for this.")
    fake_claude.handlers[EvaluatorResult] = lambda kwargs: response(claim, web_searches=0)
    result = Evaluator(lens("reality_auditor"), IDEA).evaluate()
    assert result["status"] == "success"
    assert len(result["warnings"]) == 1
    assert "made no search" in result["warnings"][0]
    assert "I searched for this." in result["warnings"][0]


def test_a_plain_result_has_no_warnings(fake_claude):
    assert Evaluator(lens("reality_auditor"), IDEA).evaluate()["warnings"] == []
