"""
Anthropic client shared by the lenses and the synthesis.

Every API response carries anthropic-ratelimit-* headers (requests and tokens
remaining in the current window, and when it resets). messages.parse() does not
expose response headers, so an HTTP response hook logs them at DEBUG; the log file
then shows how close a run came to the rate limits.
"""

import logging
from functools import lru_cache

from anthropic import Anthropic, DefaultHttpxClient

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

RATE_LIMIT_HEADER_PREFIX = "anthropic-ratelimit-"


def _log_rate_limits(response) -> None:
    limits = {
        name[len(RATE_LIMIT_HEADER_PREFIX):]: value
        for name, value in response.headers.items()
        if name.lower().startswith(RATE_LIMIT_HEADER_PREFIX)
    }
    if limits:
        logger.debug(
            f"rate limits after HTTP {response.status_code}: "
            + ", ".join(f"{name}={value}" for name, value in sorted(limits.items()))
        )


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    """One client per process: it reuses connections and is safe to share across threads."""
    return Anthropic(
        api_key=ANTHROPIC_API_KEY,
        http_client=DefaultHttpxClient(event_hooks={"response": [_log_rate_limits]}),
    )
