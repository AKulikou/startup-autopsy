"""
One structured-output request to Claude, shared by the lenses and the synthesis.

A schema-valid response can still be garbage: in one real run the model broke off
the analysis mid-sentence and filled the remaining fields with fragments
("killer_risk": "none", empty lists). Each caller passes a validator; output it
rejects is retried once, then reported as an error instead of reaching a report.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
# A server-side tool loop (web search) can pause a long turn; resume it this many times.
MAX_CONTINUATIONS = 3

ResultT = TypeVar("ResultT", bound=BaseModel)


class InvalidResultError(RuntimeError):
    """Raised when the model keeps returning structurally valid but unusable output."""

    def __init__(self, message: str, input_tokens: int, output_tokens: int):
        super().__init__(message)
        # The rejected attempts are billed, so callers still report their tokens.
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def length_problems(field: str, text: str, min_chars: int, max_chars: int) -> list[str]:
    """A too short or too long field is a sign of truncated or bled-over output."""
    length = len(text.strip())
    if length < min_chars:
        return [f"{field} too short ({text.strip()!r})"]
    if length > max_chars:
        return [f"{field} too long ({length} chars, starts {text.strip()[:60]!r})"]
    return []


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
    web_searches: int = 0  # billed per search, on top of tokens


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
    thinking: bool = False,
    tools: list[dict] | None = None,
) -> StructuredResponse[ResultT]:
    """
    Send the request, check why generation stopped, and validate the parsed result.
    With `thinking`, the model uses adaptive thinking before answering. `tools` are
    server-side tools (web search); a turn they pause is resumed up to
    MAX_CONTINUATIONS times.

    Raises:
        RuntimeError: on truncation or refusal
        InvalidResultError: if every attempt returned output rejected by `validate`
        anthropic.APIError: on API failures (the SDK has already retried transient ones)
    """
    input_tokens = 0
    output_tokens = 0
    web_searches = 0
    extra = {"thinking": {"type": "adaptive"}} if thinking else {}
    if tools:
        extra["tools"] = tools
    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.debug(
            f"{label}: request model={model} max_tokens={max_tokens} thinking={thinking} "
            f"tools={[t['name'] for t in tools or []]} "
            f"system_chars={len(system)} user_chars={len(user)}"
        )
        messages = [{"role": "user", "content": user}]
        paused_content = []
        for continuation in range(MAX_CONTINUATIONS + 1):
            response = client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_format=output_format,
                **extra,
            )
            server_tools = getattr(response.usage, "server_tool_use", None)
            searches = getattr(server_tools, "web_search_requests", 0) or 0
            logger.debug(
                f"{label}: response request_id={response._request_id} "
                f"stop_reason={response.stop_reason} input_tokens={response.usage.input_tokens} "
                f"output_tokens={response.usage.output_tokens} web_searches={searches}"
            )
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            web_searches += searches
            if response.stop_reason != "pause_turn":
                break
            if continuation == MAX_CONTINUATIONS:
                raise RuntimeError(
                    f"Server tool turn still paused after {MAX_CONTINUATIONS} continuations"
                )
            # The API resumes from the trailing server_tool_use block; no extra user message.
            paused_content += response.content
            messages = [{"role": "user", "content": user}, {"role": "assistant", "content": paused_content}]

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Response truncated at max_tokens={max_tokens}; increase MAX_TOKENS in config.py"
            )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model refused the request")

        problems = validate(response.parsed_output)
        if not problems:
            return StructuredResponse(response.parsed_output, input_tokens, output_tokens, web_searches)
        logger.warning(
            f"{label}: invalid result on attempt {attempt}/{MAX_ATTEMPTS} "
            f"(request_id={response._request_id}): {'; '.join(problems)}"
        )

    raise InvalidResultError(
        f"{MAX_ATTEMPTS} attempts returned malformed output: {'; '.join(problems)}",
        input_tokens,
        output_tokens,
    )
