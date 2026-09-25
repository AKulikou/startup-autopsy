"""Optional report translation: off by default, never touches the English reports."""

import pytest

from core import analysis_runner
from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor
from core.translator import translate_markdown

from conftest import text_response

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
    assert list(run_dir.rglob("*.russian.md")) == []
    assert text_calls(fake_claude) == []


def test_main_report_is_translated_next_to_the_english_one(fake_claude, run_idea):
    ok, run_dir = run_idea("Russian")
    english = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Verdict:" in english
    assert (run_dir / "report.russian.md").read_text(encoding="utf-8").startswith("ПЕРЕВЕДЁННЫЙ ОТЧЁТ")
    assert list((run_dir / "lenses").glob("*.russian.md")) == []
    assert len(text_calls(fake_claude)) == 1
    assert "Russian" in text_calls(fake_claude)[0]["system"]
    assert text_calls(fake_claude)[0]["model"] == "claude-haiku-4-5"
    assert text_calls(fake_claude)[0]["messages"][0]["content"] == english


def test_lens_reports_are_translated_only_when_asked(fake_claude, run_idea):
    ok, run_dir = run_idea("Russian", lens_reports=True)
    english_lenses = [p for p in (run_dir / "lenses").glob("*.md") if ".russian." not in p.name]
    assert len(list((run_dir / "lenses").glob("*.russian.md"))) == len(english_lenses)


def test_failed_translation_leaves_the_english_report_and_the_run_succeeds(fake_claude, run_idea):
    def fail(kwargs):
        raise ConnectionError("Connection error.")
    fake_claude.create_handler = fail
    ok, run_dir = run_idea("Russian")
    assert ok
    assert (run_dir / "report.md").exists()
    assert not (run_dir / "report.russian.md").exists()


def test_truncated_translation_is_an_error_not_a_half_report(fake_claude):
    fake_claude.create_handler = lambda kw: text_response("Половина", stop_reason="max_tokens")
    outcome = translate_markdown("# Report", "Russian")
    assert outcome["status"] == "error" and "max_tokens" in outcome["error"]
    assert outcome["output_tokens"] == 4000  # billed even though unusable


def test_the_eval_path_never_translates(fake_claude, monkeypatch):
    monkeypatch.setattr(analysis_runner, "REPORT_TRANSLATION", "Russian")
    AnalysisRunner(processor=None).analyze(IDEA)
    assert text_calls(fake_claude) == []
