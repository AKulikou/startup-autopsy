import pytest
from conftest import FakeClaude, lens_result, response

from core.structured_call import (
    InvalidResultError,
    billed_tokens,
    length_problems,
    request_structured,
)
from evaluators.evaluator import validate_result
from evaluators.schemas import EvaluatorResult

# The malformed answer a real run returned: analysis cut at a double quote,
# the other fields filled with fragments.
GARBAGE = lens_result(
    analysis="## Revenue lens ... The pitch says ",
    summary="hope customs don't charge 50%",
    confidence_reason=" Hi nges on unver ified",
    killer_risk=" none",
    key_assumptions=[],
    next_steps=[],
)


def call(client):
    return request_structured(
        client, label="Test lens", model="claude-test", max_tokens=16000,
        system="system", user="user", output_format=EvaluatorResult, validate=validate_result,
    )


def scripted(*answers) -> FakeClaude:
    client = FakeClaude()
    queue = list(answers)
    client.handlers[EvaluatorResult] = lambda kwargs: queue.pop(0)
    return client


def test_valid_answer_is_returned_with_its_tokens():
    result = call(scripted(response(lens_result(), input_tokens=100, output_tokens=50)))
    assert result.result.verdict == "NEEDS_VALIDATION"
    assert (result.input_tokens, result.output_tokens) == (100, 50)


def test_malformed_answer_is_retried_and_both_attempts_are_billed():
    client = scripted(
        response(GARBAGE, input_tokens=100, output_tokens=50),
        response(lens_result(), input_tokens=100, output_tokens=50),
    )
    result = call(client)
    assert len(client.requests) == 2
    assert (result.input_tokens, result.output_tokens) == (200, 100)


def test_two_malformed_answers_raise_with_the_billed_tokens():
    with pytest.raises(InvalidResultError) as error:
        call(scripted(
            response(GARBAGE, input_tokens=100, output_tokens=50),
            response(GARBAGE, input_tokens=100, output_tokens=50),
        ))
    assert "killer_risk is a placeholder" in str(error.value)
    assert billed_tokens(error.value) == {"input_tokens": 200, "output_tokens": 100}


@pytest.mark.parametrize("stop_reason, message", [("max_tokens", "truncated"), ("refusal", "refused")])
def test_truncated_or_refused_answers_are_errors_not_results(stop_reason, message):
    with pytest.raises(RuntimeError, match=message):
        call(scripted(response(lens_result(), stop_reason=stop_reason)))


def test_validation_catches_every_sign_of_the_real_malformed_answer():
    problems = validate_result(GARBAGE)
    assert any("analysis too short" in p for p in problems)
    assert any("summary too short" in p for p in problems)
    assert any("confidence_reason too short" in p for p in problems)
    assert "no key_assumptions" in problems and "no next_steps" in problems


def test_validation_catches_an_analysis_that_bled_into_the_summary():
    bled = lens_result(analysis="Section 1 cut short at a quote", summary="API limits? " + "text " * 400)
    problems = validate_result(bled)
    assert any("analysis too short" in p for p in problems)
    assert any("summary too long" in p for p in problems)


def test_a_normal_answer_passes_validation():
    assert validate_result(lens_result()) == []


def test_length_problems_bounds():
    assert length_problems("f", "x" * 10, 5, 20) == []
    assert "too short" in length_problems("f", "x", 5, 20)[0]
    assert "too long" in length_problems("f", "x" * 30, 5, 20)[0]


def test_thinking_is_off_unless_requested():
    client = scripted(response(lens_result()))
    call(client)
    assert "thinking" not in client.requests[0]


def test_thinking_requests_adaptive_thinking():
    client = scripted(response(lens_result()))
    request_structured(
        client, label="Test lens", model="claude-test", max_tokens=16000,
        system="system", user="user", output_format=EvaluatorResult, validate=validate_result,
        thinking=True,
    )
    assert client.requests[0]["thinking"] == {"type": "adaptive"}
