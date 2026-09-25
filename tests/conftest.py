"""
Shared test fixtures. No test calls the Anthropic API: a fake client stands in
for it and answers each structured request according to the test's script.
"""

import os
from types import SimpleNamespace

# config.py refuses to import without a plausible key; tests never use it.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-not-used")

import pytest  # noqa: E402

from evaluators import evaluator as evaluator_module  # noqa: E402
from evaluators.schemas import EvaluatorResult  # noqa: E402
from gate import idea_gate as gate_module  # noqa: E402
from gate.schemas import GateResult  # noqa: E402
from synthesis import synthesizer as synthesizer_module  # noqa: E402
from synthesis.schemas import SynthesisResult  # noqa: E402


def lens_result(**overrides) -> EvaluatorResult:
    """A lens answer that passes validation."""
    fields = dict(
        analysis="A thorough lens analysis. " * 80,
        summary="The idea is plausible within this lens but depends on untested demand.",
        verdict="NEEDS_VALIDATION",
        confidence="MEDIUM",
        confidence_reason="Hinges on whether customers pay the stated price.",
        key_assumptions=[{"statement": "s", "how_to_test": "t", "failure_signal": "f"}],
        killer_risk="Customers keep using the free alternative they already have.",
        next_steps=["Interview ten target customers."],
        out_of_lens_red_flags=[],
    )
    fields.update(overrides)
    return EvaluatorResult(**fields)


def synthesis_result(**overrides) -> SynthesisResult:
    """A synthesis answer that passes validation."""
    fields = dict(
        reasoning="The lenses agree that demand is the deciding open question. " * 10,
        verdict="NEEDS_VALIDATION",
        confidence="MEDIUM",
        confidence_reason="Depends on an untested willingness to pay.",
        summary="Needs validation: the problem is real but nobody has shown they will pay for it yet.",
        deciding_factors=[{"finding": "Willingness to pay is untested.", "lenses": ["Reality Auditor"]}],
        killer_risks=[{"finding": "Free alternatives are good enough.", "lenses": []}],
        conflicts=[],
        key_assumptions=[{"statement": "s", "how_to_test": "t", "failure_signal": "f"}],
        next_steps=["Interview ten target customers."],
    )
    fields.update(overrides)
    return SynthesisResult(**fields)


def gate_result(decision="ANALYZABLE", **overrides) -> GateResult:
    fields = dict(
        reason="A concrete product sold to a named customer.",
        decision=decision,
        missing_information=["target customer"] if decision == "TOO_VAGUE" else [],
        injection_suspected=False,
    )
    fields.update(overrides)
    return GateResult(**fields)


def response(parsed, stop_reason="end_turn", input_tokens=1000, output_tokens=500):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        _request_id="req_test",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeClaude:
    """
    Answers messages.parse() by output schema. Each handler takes the request
    kwargs and returns a response() or raises. Every request is recorded.
    """

    def __init__(self):
        self.requests = []
        self.handlers = {
            GateResult: lambda kwargs: response(gate_result()),
            EvaluatorResult: lambda kwargs: response(lens_result()),
            SynthesisResult: lambda kwargs: response(synthesis_result()),
        }
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.requests.append(kwargs)
        return self.handlers[kwargs["output_format"]](kwargs)

    def calls(self, schema) -> list[dict]:
        return [r for r in self.requests if r["output_format"] is schema]


@pytest.fixture
def fake_claude(monkeypatch) -> FakeClaude:
    """Replace the shared Anthropic client in every module that makes API calls."""
    fake = FakeClaude()
    for module in (evaluator_module, synthesizer_module, gate_module):
        monkeypatch.setattr(module, "get_client", lambda: fake)
    return fake
