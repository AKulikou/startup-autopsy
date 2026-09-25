"""
Local preparation of an idea's text before any API call.

Rejects input that cannot be a business idea (empty, or almost no letters) so a
run does not spend money on it, and replaces straight double quotes with
typographic ones: models tend to copy quoted phrases from the idea into their
JSON answer, and an unescaped straight quote there ends the field early.
The quotes are replaced, not removed, because they often carry meaning.
"""

import re

# Texts with fewer letters are not analyzed at all, whatever they say: too short to
# describe a business ("ABC123", "birds sing"). Longer texts go to the Claude-based
# input check, which judges their meaning.
MIN_LETTERS = 15

_QUOTED = re.compile(r'"([^"\n]*)"')


class InvalidIdeaError(ValueError):
    """Raised when the idea text cannot be analyzed at all."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # "EMPTY" or "TOO_SHORT", for callers that branch on the reason


def prepare_idea(text: str) -> tuple[str, int]:
    """
    Validate the idea text and normalize its quotes.

    Returns:
        (prepared text, number of straight double quotes replaced)

    Raises:
        InvalidIdeaError: if the text is empty or has too few letters
    """
    stripped = text.strip()
    if not stripped:
        raise InvalidIdeaError("EMPTY", "The idea file is empty.")

    letters = sum(char.isalpha() for char in stripped)
    if letters < MIN_LETTERS:
        raise InvalidIdeaError(
            "TOO_SHORT",
            f"Too short to analyze: {letters} letters, at least {MIN_LETTERS} are needed.",
        )

    replaced = stripped.count('"')
    prepared = _QUOTED.sub(r"“\1”", stripped).replace('"', "”")
    return prepared, replaced
