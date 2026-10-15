"""Optional report translation: off by default, never touches the English reports."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import text_response

from core import analysis_runner
from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor
from core.translator import translate_markdown, translate_run, translated_path

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
    assert len(text_calls(fake_claude)) == 1
    assert "Lithuanian" in text_calls(fake_claude)[0]["system"]
    assert text_calls(fake_claude)[0]["model"] == "claude-haiku-5-5"
    assert text_calls(fake_claude)[0]["output_config"] == {"effort": "low"}
    assert text_calls(fake_claude)[0]["messages"][0]["content"] == english


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
