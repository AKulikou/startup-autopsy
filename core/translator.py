"""
Optional translation of finished reports for readers who prefer another language.

The analysis itself always runs in English, and the English reports stay the
source of truth: translation is a separate step over a finished run directory,
so it cannot change a verdict or an eval result. Any language name Claude
understands works (Lithuanian, German, Japanese, ...); the CLI takes it from
.env, the MCP server from the calling client, and an existing translation is
reused rather than paid for twice.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import MAX_TOKENS, TRANSLATION_EFFORT, TRANSLATION_MODEL
from core.claude_client import get_client
from core.result_writer import LENSES_DIR, REPORT_FILENAME
from core.token_summary import estimate_cost, format_cost

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
            model=TRANSLATION_MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": TRANSLATION_EFFORT},
            system=TRANSLATION_PROMPT.format(language=language),
            messages=[{"role": "user", "content": markdown}],
        )
        usage = {
            "model": TRANSLATION_MODEL,
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
                "model": TRANSLATION_MODEL, "duration_s": time.monotonic() - started}


def needs_translation(language: str | None) -> bool:
    """False for no language or English: the reports are already in English."""
    return bool(language and language.strip()) and language.strip().lower() not in ("english", "en")


def translated_path(path: Path, language: str) -> Path:
    """report.md + 'Lithuanian' -> report.lithuanian.md (spaces become underscores)."""
    suffix = language.strip().lower().replace(" ", "_")
    return path.with_name(f"{path.stem}.{suffix}.md")


def english_reports(run_dir: Path, lens_reports: bool) -> list[Path]:
    """The English reports of a run: report.md, plus the lens reports if asked."""
    paths = [run_dir / REPORT_FILENAME]
    if lens_reports:
        # English lens reports have one dot (name.md); translations have two.
        paths += sorted(p for p in (run_dir / LENSES_DIR).glob("*.md") if p.name.count(".") == 1)
    return paths


def translate_run(run_dir: Path, language: str, lens_reports: bool = False) -> list[dict]:
    """
    Write <name>.<language>.md next to the English reports of a finished run.

    A translation that already exists is kept and not requested again. A failed
    translation is logged and skipped; the English reports are never touched.
    Returns the outcome of each translation call made (for the token summary).
    """
    todo = [p for p in english_reports(run_dir, lens_reports) if not translated_path(p, language).exists()]
    if not todo:
        logger.info(f"[Translation] {language}: already translated, nothing to do")
        return []
    logger.info(f"[Translation] ... started: {len(todo)} report(s) into {language}")

    def translate(path: Path) -> dict:
        outcome = translate_markdown(path.read_text(encoding="utf-8"), language)
        outcome["evaluator_display"] = f"Translation of {path.name}"
        if outcome["status"] == "success":
            translated_path(path, language).write_text(outcome["text"], encoding="utf-8")
        return outcome

    with ThreadPoolExecutor(max_workers=len(todo)) as pool:
        outcomes = list(pool.map(translate, todo))

    for outcome in outcomes:
        if outcome["status"] != "success":
            logger.warning(f"[Translation] {outcome['evaluator_display']} FAILED: {outcome['error']}")
    done = [o for o in outcomes if o["status"] == "success"]
    if done:
        input_tokens = sum(o["input_tokens"] for o in done)
        output_tokens = sum(o["output_tokens"] for o in done)
        logger.info(
            f"[Translation] ... done: {len(done)} of {len(todo)} report(s), "
            f"{input_tokens}/{output_tokens} tokens, "
            f"{format_cost(estimate_cost(input_tokens, output_tokens, TRANSLATION_MODEL))} "
            f"({TRANSLATION_MODEL}); "
            f"main report: {translated_path(run_dir / REPORT_FILENAME, language).name}"
        )
    return outcomes
