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
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import MAX_TOKENS, TRANSLATION_EFFORT, TRANSLATION_MODEL, TRANSLATION_RETRY_EFFORT
from core.claude_client import get_client
from core.result_writer import LENSES_DIR, REPORT_FILENAME
from core.token_summary import estimate_cost, format_cost

logger = logging.getLogger(__name__)

TRANSLATION_PROMPT = """\
Translate the Markdown text below into {language}. Translate all of its text,
including headings, table headers, labels and bold lead-ins; keep the Markdown
markup and structure unchanged (heading levels, lists, tables, emphasis, links).
Do not translate link targets, numbers, currencies, units, or the names of
companies, products, laws and regulations. Keep the analyst names (such as
'Reality Auditor') and file names in English. Write the whole translation in
{language}, even where the text is about another country or names its places.
Output only the translated text.
"""

# Added to the prompt when a section is asked again after a rejected answer.
RETRY_NOTE = """
Your answer must be written entirely in {language}: every heading, sentence, list
item and table cell. Text left in English or written in any other language is a
wrong answer.
"""

# A report is translated one level-2 section at a time. In one call over a whole
# report, Haiku 5.5 kept the headings in English (the old prompt said "keep the
# headings") and once returned the last section, the synthesis reasoning,
# untranslated. Sections are short, run in parallel and can be checked one by one.
SECTION_START = re.compile(r"(?m)^(?=## )")
SECTION_WORKERS = 4
# A section counts as left untranslated when most of its words come back unchanged.
# Measured on two real Russian translations: translated sections keep 4-35% of their
# words (names, file names, links), an untranslated one 100%.
UNTRANSLATED_SHARE = 0.6
MIN_WORDS_TO_CHECK = 25
UNTRANSLATED_NOTE = "> This section could not be translated; the English original follows.\n\n"

# The overlap check cannot see a section that comes back in a third language: in one
# Russian translation of a report about Vilnius, "Next Steps" came back in Lithuanian.
# The script of the letters tells Russian from Lithuanian; for the Latin-script
# languages of the web page, letters outside the language's alphabet tell one from
# another. Other languages are not checked this way (the overlap check still runs).
SCRIPTS = {
    "russian": {"CYRILLIC"}, "ukrainian": {"CYRILLIC"}, "belarusian": {"CYRILLIC"},
    "bulgarian": {"CYRILLIC"}, "greek": {"GREEK"}, "japanese": {"CJK", "HIRAGANA", "KATAKANA"},
    "chinese": {"CJK"}, "korean": {"HANGUL"}, "arabic": {"ARABIC"}, "hebrew": {"HEBREW"},
    "hindi": {"DEVANAGARI"},
}
# The letters beyond a-z that each Latin-script language of the web page uses.
LATIN_ALPHABETS = {
    "lithuanian": "ąčęėįšųūž",
    "latvian": "āčēģīķļņšūž",
    "estonian": "äõöüšž",
    "polish": "ąćęłńóśźż",
    "german": "äöüß",
    "french": "àâæçéèêëîïôœùûüÿ",
    "spanish": "áéíñóúü",
    "italian": "àèéìíîòóù",
}
# Measured on four real Russian translations: translated sections have 75-100% of
# their letters in Cyrillic, the Lithuanian and the English sections 0%. A real name
# from another language adds a few foreign letters (3 in 4,000 were seen); the
# Lithuanian section had 115 in 1,300.
MIN_SCRIPT_SHARE = 0.3
FOREIGN_LETTER_SHARE = 0.02
MIN_FOREIGN_LETTERS = 10
HEADING_LEFT = "heading left in English"

# Put above every translated copy, in English, so a reader of any language sees
# which file is the source of truth.
MACHINE_TRANSLATION_NOTE = (
    "> Machine translation into {language} of the English original ({original}). "
    "Numbers and structure are kept; if the two differ, the English original is authoritative.\n\n"
)


def translate_markdown(markdown: str, language: str, retry: bool = False) -> dict:
    """
    Translate a Markdown document. Never raises. A retry adds RETRY_NOTE and thinks more.

    Returns:
        {"status": "success", "text": str, "input_tokens", "output_tokens", "duration_s"}
        or {"status": "error", "error": str, "duration_s", and tokens when known}
    """
    started = time.monotonic()
    try:
        response = get_client().messages.create(
            model=TRANSLATION_MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": TRANSLATION_RETRY_EFFORT if retry else TRANSLATION_EFFORT},
            system=(TRANSLATION_PROMPT + (RETRY_NOTE if retry else "")).format(language=language),
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


def split_sections(markdown: str) -> list[str]:
    """The text before the first level-2 heading, then one part per level-2 section."""
    return [part for part in SECTION_START.split(markdown) if part.strip()]


def _words(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[^\W\d_]{4,}", text)]


def looks_untranslated(source: str, translation: str) -> bool:
    """True when most words of the source come back unchanged (short parts are not judged)."""
    words = _words(source)
    if len(words) < MIN_WORDS_TO_CHECK:
        return False
    kept = set(_words(translation))
    return sum(word in kept for word in words) / len(words) >= UNTRANSLATED_SHARE


def _script(letter: str) -> str:
    """The script a letter belongs to: LATIN, CYRILLIC, CJK, ..."""
    return unicodedata.name(letter, "").split(" ", 1)[0]


def wrong_language(text: str, language: str) -> str | None:
    """Why the text is not in the language, or None (also when it cannot be told)."""
    key = language.strip().lower()
    scripts = SCRIPTS.get(key) or ({"LATIN"} if key in LATIN_ALPHABETS else None)
    letters = [c for c in text if c.isalpha()]
    if not scripts or not letters:
        return None
    if sum(_script(c) in scripts for c in letters) / len(letters) < MIN_SCRIPT_SHARE:
        return "written in another script"
    alphabet = LATIN_ALPHABETS.get(key)
    if alphabet is not None:
        foreign = [
            c for c in letters if not c.isascii() and _script(c) == "LATIN" and c.lower() not in alphabet
        ]
        if len(foreign) >= MIN_FOREIGN_LETTERS and len(foreign) / len(letters) >= FOREIGN_LETTER_SHARE:
            return "letters of another language"
    return None


def _heading(text: str) -> str:
    return text.strip().split("\n", 1)[0].strip()


def heading_untranslated(source: str, translation: str) -> bool:
    """True when a section heading of two or more words comes back unchanged."""
    heading = _heading(source)
    return (heading.startswith("## ") and len(_words(heading)) >= 2
            and _heading(translation).lower() == heading.lower())


def section_problem(source: str, translation: str, language: str) -> str | None:
    """Why a translated section cannot be used as it is, or None."""
    if looks_untranslated(source, translation):
        return "left in English"
    if len(_words(source)) >= MIN_WORDS_TO_CHECK:
        wrong = wrong_language(translation, language)
        if wrong:
            return f"not in {language}: {wrong}"
    if heading_untranslated(source, translation):
        return HEADING_LEFT
    return None


def _translate_section(section: str, language: str) -> dict:
    """
    One section; asked again once, with a stricter prompt, if the answer is rejected.
    Never raises. A translation whose only fault is an English heading beats the
    English original; anything worse keeps the English section, marked.
    """
    first = translate_markdown(section, language)
    if first["status"] != "success":
        return {**first, "calls": 1, "untranslated": False}
    first_problem = section_problem(section, first["text"], language)
    if first_problem is None:
        return {**first, "calls": 1, "untranslated": False}
    heading = _heading(section)
    _log_rejected(heading, first_problem, first["text"])
    second = translate_markdown(section, language, retry=True)
    billed = {key: first.get(key, 0) + second.get(key, 0) for key in ("input_tokens", "output_tokens")}
    attempts = [(first, first_problem)]
    if second["status"] == "success":
        second_problem = section_problem(section, second["text"], language)
        if second_problem is None:
            return {**second, **billed, "calls": 2, "untranslated": False}
        _log_rejected(heading, second_problem, second["text"])
        attempts.append((second, second_problem))
    for attempt, problem in attempts:
        if problem == HEADING_LEFT:
            logger.warning(f"[Translation] '{heading}': the heading stayed English after a retry")
            return {**attempt, **billed, "calls": 2, "untranslated": False}
    logger.warning(f"[Translation] '{heading}' kept in English after a retry ({attempts[-1][1]})")
    return {"status": "success", "text": UNTRANSLATED_NOTE + section, "model": TRANSLATION_MODEL,
            **billed, "calls": 2, "untranslated": True}


def _log_rejected(heading: str, problem: str, text: str) -> None:
    """The start of a rejected answer goes to the debug log, to see what came back."""
    logger.debug(f"[Translation] '{heading}' rejected ({problem}): {text[:300]!r}")


def translate_document(markdown: str, language: str) -> dict:
    """
    Translate a report section by section and put it back together. Never raises.

    Returns the same fields as translate_markdown, with tokens summed over every call,
    plus "untranslated_sections": how many sections stayed English after a retry.
    A failed call fails the whole document: a translation with holes is not offered.
    """
    started = time.monotonic()
    sections = split_sections(markdown)
    if not sections:
        return translate_markdown(markdown, language)
    with ThreadPoolExecutor(max_workers=min(SECTION_WORKERS, len(sections))) as pool:
        outcomes = list(pool.map(lambda section: _translate_section(section, language), sections))
    billed = {
        "model": TRANSLATION_MODEL,
        "input_tokens": sum(o.get("input_tokens", 0) for o in outcomes),
        "output_tokens": sum(o.get("output_tokens", 0) for o in outcomes),
        "duration_s": time.monotonic() - started,
    }
    failed = [o for o in outcomes if o["status"] != "success"]
    if failed:
        return {"status": "error", "error": failed[0]["error"], **billed}
    untranslated = sum(o["untranslated"] for o in outcomes)
    text = "\n\n".join(o["text"].strip() for o in outcomes) + "\n"
    return {"status": "success", "text": text, "untranslated_sections": untranslated, **billed}


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
        outcome = translate_document(path.read_text(encoding="utf-8"), language)
        outcome["evaluator_display"] = f"Translation of {path.name}"
        if outcome["status"] == "success":
            note = MACHINE_TRANSLATION_NOTE.format(language=language, original=path.name)
            translated_path(path, language).write_text(note + outcome["text"], encoding="utf-8")
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
