"""
Optional translation of finished reports for readers who prefer another language.

The analysis itself always runs in English, and the English reports stay the
source of truth: translation is a separate call made after they are written,
so it cannot change a verdict or an eval result.
"""

import logging
import time

from config import MAX_TOKENS, MODEL
from core.claude_client import get_client

logger = logging.getLogger(__name__)

TRANSLATION_PROMPT = """\
Translate the Markdown document below into {language}.
Keep the Markdown structure exactly: headings, lists, tables, emphasis and links.
Do not translate link targets, numbers, currencies, units, or the names of
companies, products, laws and regulations. Keep the analyst names (such as
'Reality Auditor') in English. Output only the translated document.
"""


def translate_markdown(markdown: str, language: str) -> dict:
    """
    Translate a Markdown document. Never raises.

    Returns:
        {"status": "success", "text": str, "input_tokens", "output_tokens", "duration_s"}
        or {"status": "error", "error": str, "duration_s", and tokens when known}
    """
    started = time.monotonic()
    try:
        response = get_client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=TRANSLATION_PROMPT.format(language=language),
            messages=[{"role": "user", "content": markdown}],
        )
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        if response.stop_reason != "end_turn":
            return {"status": "error", "error": f"translation stopped: {response.stop_reason}",
                    "duration_s": time.monotonic() - started, **usage}
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            return {"status": "error", "error": "empty translation",
                    "duration_s": time.monotonic() - started, **usage}
        return {"status": "success", "text": text + "\n",
                "duration_s": time.monotonic() - started, **usage}
    except Exception as e:
        logger.debug("Translation failed", exc_info=True)
        return {"status": "error", "error": f"{type(e).__name__}: {e}",
                "duration_s": time.monotonic() - started}
