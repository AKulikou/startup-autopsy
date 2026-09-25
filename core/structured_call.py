"""
One structured-output request to Claude, shared by the lenses and the synthesis.

A schema-valid response can still be garbage: in one real run the model broke off
the analysis mid-sentence and filled the remaining fields with fragments
("killer_risk": "none", empty lists). Each caller passes a validator; output it
rejects is retried once, then reported as an error instead of reaching a report.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2

ResultT = TypeVar("ResultT", bound=BaseModel)


class InvalidResultError(RuntimeError):
    """Raised when the model keeps returning structurally valid but unusable output."""

    def __init__(self, message: str, input_tokens: int, output_tokens: int):
        super().__init__(message)
        # The rejected attempts are billed, so callers still report their tokens.
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def billed_tokens(error: Exception) -> dict:
    """Token fields for an error result: rejected attempts are billed, other failures are not known."""
    if isinstance(error, InvalidResultError):
        return {"input_tokens": error.input_tokens, "output_tokens": error.output_tokens}
    return {}


@dataclass
class StructuredResponse(Generic[ResultT]):
    result: ResultT
    input_tokens: int  # summed over all attempts: discarded attempts are billed too
    output_tokens: int


def request_structured(
    client: Anthropic,
    *,
    label: str,
    model: str,
    max_tokens: int,
    system: str,
    user: str,
    output_format: type[ResultT],
    validate: Callable[[ResultT], list[str]],
) -> StructuredResponse[ResultT]:
    """
    Send the request, check why generation stopped, and validate the parsed result.

    Raises:
        RuntimeError: on truncation or refusal
        InvalidResultError: if every attempt returned output rejected by `validate`
        anthropic.APIError: on API failures (the SDK has already retried transient ones)
    """
    input_tokens = 0
    output_tokens = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.debug(
            f"{label}: request model={model} max_tokens={max_tokens} "
            f"system_chars={len(system)} user_chars={len(user)}"
        )
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_format,
        )
        logger.debug(
            f"{label}: response request_id={response._request_id} "
            f"stop_reason={response.stop_reason} input_tokens={response.usage.input_tokens} "
            f"output_tokens={response.usage.output_tokens}"
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Response truncated at max_tokens={max_tokens}; increase MAX_TOKENS in config.py"
            )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model refused the request")

        problems = validate(response.parsed_output)
        if not problems:
            return StructuredResponse(response.parsed_output, input_tokens, output_tokens)
        logger.warning(
            f"{label}: invalid result on attempt {attempt}/{MAX_ATTEMPTS} "
            f"(request_id={response._request_id}): {'; '.join(problems)}"
        )

    raise InvalidResultError(
        f"{MAX_ATTEMPTS} attempts returned malformed output: {'; '.join(problems)}",
        input_tokens,
        output_tokens,
    )
