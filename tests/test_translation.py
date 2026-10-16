"""Optional report translation: off by default, never touches the English reports."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import text_response

from core import analysis_runner
from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor
from core.translator import (
    TRANSLATION_PROMPT,
    UNTRANSLATED_NOTE,
    looks_untranslated,
    split_sections,
    translate_document,
    translate_markdown,
    translate_run,
    translated_path,
)

IDEA = "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week, ordered online."


@pytest.fixture
def run_idea(tmp_path, monkeypatch):
    """Run the full CLI path on one idea and return the run directory."""
    ideas = tmp_path / "ideas"
    ideas.mkdir()
    (ideas / "meals.txt").write_text(IDEA, encoding="utf-8")
    results = tmp_path / "results"

    def run(language=None, lens_reports=False):
        monkeypatch.setattr(analysis_runner, "REPORT_TRANSLATION", language)
        monkeypatch.setattr(analysis_runner, "TRANSLATE_LENS_REPORTS", lens_reports)
        processor = IdeaProcessor(ideas_dir=str(ideas), results_dir=str(results))
        ok = AnalysisRunner(processor).run("meals")
        return ok, next(results.iterdir())

    return run


def text_calls(fake):
    return [r for r in fake.requests if r["output_format"] is None]


def test_no_translation_by_default(fake_claude, run_idea):
    ok, run_dir = run_idea()
    assert ok
    assert (run_dir / "report.md").exists()
    assert list(run_dir.rglob("*.lithuanian.md")) == []
    assert text_calls(fake_claude) == []


def test_main_report_is_translated_next_to_the_english_one(fake_claude, run_idea):
    ok, run_dir = run_idea("Lithuanian")
    english = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Verdict:" in english
    translated = (run_dir / "report.lithuanian.md").read_text(encoding="utf-8")
    assert translated.startswith("> Machine translation into Lithuanian of the English original (report.md).")
    assert translated.endswith("IŠVERSTA ATASKAITA\n")
    assert list((run_dir / "lenses").glob("*.lithuanian.md")) == []
    calls = text_calls(fake_claude)
    # One call per level-2 section; together they cover the whole English report.
    assert len(calls) == len(split_sections(english)) > 1
    assert sorted(c["messages"][0]["content"] for c in calls) == sorted(split_sections(english))
    assert "".join(split_sections(english)) == english
    assert all("Lithuanian" in c["system"] for c in calls)
    assert {c["model"] for c in calls} == {"claude-haiku-5-5"}
    assert all(c["output_config"] == {"effort": "low"} for c in calls)


def test_lens_reports_are_translated_only_when_asked(fake_claude, run_idea):
    ok, run_dir = run_idea("Lithuanian", lens_reports=True)
    english_lenses = [p for p in (run_dir / "lenses").glob("*.md") if ".lithuanian." not in p.name]
    assert len(list((run_dir / "lenses").glob("*.lithuanian.md"))) == len(english_lenses)


def test_failed_translation_leaves_the_english_report_and_the_run_succeeds(fake_claude, run_idea):
    def fail(kwargs):
        raise ConnectionError("Connection error.")
    fake_claude.create_handler = fail
    ok, run_dir = run_idea("Lithuanian")
    assert ok
    assert (run_dir / "report.md").exists()
    assert not (run_dir / "report.lithuanian.md").exists()


def test_truncated_translation_is_an_error_not_a_half_report(fake_claude):
    fake_claude.create_handler = lambda kw: text_response("Pusė", stop_reason="max_tokens")
    outcome = translate_markdown("# Report", "Lithuanian")
    assert outcome["status"] == "error" and "max_tokens" in outcome["error"]
    assert outcome["output_tokens"] == 4000  # billed even though unusable


def test_thinking_blocks_before_the_text_are_not_part_of_the_translation(fake_claude):
    # Haiku 5.5 thinks by default; its thinking blocks come back with empty text.
    answer = text_response("Ataskaita")
    answer.content.insert(0, SimpleNamespace(type="thinking", thinking="", signature="sig"))
    fake_claude.create_handler = lambda kw: answer
    outcome = translate_markdown("# Report", "Lithuanian")
    assert outcome["status"] == "success" and outcome["text"] == "Ataskaita\n"


def test_the_eval_path_never_translates(fake_claude, monkeypatch):
    monkeypatch.setattr(analysis_runner, "REPORT_TRANSLATION", "Lithuanian")
    AnalysisRunner(processor=None).analyze(IDEA)
    assert text_calls(fake_claude) == []


def test_english_means_no_translation(fake_claude, run_idea):
    ok, run_dir = run_idea("English")
    assert ok
    assert text_calls(fake_claude) == []


def test_an_existing_translation_is_reused_not_paid_for_again(fake_claude, run_idea):
    ok, run_dir = run_idea("Lithuanian", lens_reports=True)
    calls = len(text_calls(fake_claude))
    assert translate_run(run_dir, "Lithuanian", lens_reports=True) == []
    assert len(text_calls(fake_claude)) == calls


def test_a_second_language_is_added_next_to_the_first(fake_claude, run_idea):
    ok, run_dir = run_idea("Lithuanian", lens_reports=True)
    lens_count = len(list((run_dir / "lenses").glob("*.lithuanian.md")))
    translate_run(run_dir, "German", lens_reports=True)
    assert (run_dir / "report.german.md").exists()
    # Earlier translations are not mistaken for English reports to translate.
    assert len(list((run_dir / "lenses").glob("*.german.md"))) == lens_count
    assert list(run_dir.rglob("*.lithuanian.german.md")) == []


def test_translated_file_name_comes_from_the_language_name():
    assert translated_path(Path("run/report.md"), " Lithuanian ") == Path("run/report.lithuanian.md")


# Section by section: headings translated, no section quietly left in English.

REPORT = (
    "# Startup Autopsy — meals\n\n- **Model:** claude-sonnet-4-6\n\n"
    "## Verdict: Needs validation\n\nThe demand for weekly meal delivery is real but unproven "
    "among office workers, and the price has not been tested with paying customers yet.\n\n"
    "## Appendix: How the Verdict Was Reached\n\nEvery lens agreed that willingness to pay is the "
    "deciding question, while the delivery logistics look manageable for a small team at first. "
    "The revenue lens doubted the price, the launch lens doubted the first week, and the reality "
    "check asked for ten paying customers before any further spending on the kitchen.\n"
)


def fake_translator(untranslated_first: int = 0):
    """Answers each section with a 'translation'; the first N answers return it unchanged."""
    answers = {"left": untranslated_first}

    def handler(kwargs):
        source = kwargs["messages"][0]["content"]
        if answers["left"] > 0 and "Appendix" in source:
            answers["left"] -= 1
            return text_response(source)
        heading = source.splitlines()[0]
        return text_response(f"{heading} (LT)\n\nIšversta dalis.")

    return handler


def test_the_prompt_asks_for_headings_to_be_translated_too():
    assert "including headings" in TRANSLATION_PROMPT


def test_a_report_splits_before_each_level_two_heading():
    parts = split_sections(REPORT)
    assert [p.splitlines()[0] for p in parts] == [
        "# Startup Autopsy — meals",
        "## Verdict: Needs validation",
        "## Appendix: How the Verdict Was Reached",
    ]
    assert "".join(parts) == REPORT


def test_sections_are_translated_and_put_back_in_order(fake_claude):
    fake_claude.create_handler = fake_translator()
    outcome = translate_document(REPORT, "Lithuanian")
    assert outcome["status"] == "success" and outcome["untranslated_sections"] == 0
    headings = [line for line in outcome["text"].splitlines() if line.startswith("#")]
    assert headings == ["# Startup Autopsy — meals (LT)", "## Verdict: Needs validation (LT)",
                        "## Appendix: How the Verdict Was Reached (LT)"]
    assert outcome["input_tokens"] == 3 * 3000  # summed over the three calls


def test_a_section_returned_in_english_is_retried_once(fake_claude):
    fake_claude.create_handler = fake_translator(untranslated_first=1)
    outcome = translate_document(REPORT, "Lithuanian")
    assert "## Appendix: How the Verdict Was Reached (LT)" in outcome["text"]
    assert outcome["untranslated_sections"] == 0
    assert len(text_calls(fake_claude)) == 4  # three sections, one retry
    assert outcome["output_tokens"] == 4 * 4000  # the rejected answer is billed too


def test_a_section_still_english_after_the_retry_is_kept_and_marked(fake_claude):
    fake_claude.create_handler = fake_translator(untranslated_first=2)
    outcome = translate_document(REPORT, "Lithuanian")
    assert outcome["status"] == "success" and outcome["untranslated_sections"] == 1
    assert UNTRANSLATED_NOTE + "## Appendix: How the Verdict Was Reached" in outcome["text"]


def test_one_failed_section_fails_the_whole_translation(fake_claude):
    def fails_on_appendix(kwargs):
        if "Appendix" in kwargs["messages"][0]["content"]:
            raise ConnectionError("Connection error.")
        return text_response("Išversta dalis.")

    fake_claude.create_handler = fails_on_appendix
    outcome = translate_document(REPORT, "Lithuanian")
    assert outcome["status"] == "error" and "Connection error" in outcome["error"]


def test_untranslated_text_is_recognised_and_names_alone_are_not():
    english = "Every lens agreed that willingness to pay is the deciding question. " * 4
    assert looks_untranslated(english, english)
    assert not looks_untranslated(english, "Visi vertinimai sutarė, kad mokumas yra lemiamas klausimas. " * 4)
    assert not looks_untranslated("Reality Auditor", "Reality Auditor")  # too short to judge
