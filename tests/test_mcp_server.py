"""The MCP tools, called in-process through the server with a fake Claude."""

import asyncio
from pathlib import Path

import pytest
from conftest import gate_result, response

import mcp_server
from evaluators.schemas import EvaluatorResult
from gate.schemas import GateResult

IDEA = "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week, ordered online."


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    """Keep reports written by analyze_idea out of the real results/ folder."""
    monkeypatch.setattr(mcp_server, "RESULTS_DIR", tmp_path / "results")
    return tmp_path / "results"


def call(tool, **arguments) -> dict:
    result = asyncio.run(mcp_server.server.call_tool(tool, arguments))
    assert not result.is_error
    return result.structured_content


def test_both_tools_are_listed_with_output_schemas():
    tools = {t.name: t for t in asyncio.run(mcp_server.server.list_tools())}
    assert set(tools) == {"check_idea", "analyze_idea"}
    assert all(t.output_schema for t in tools.values())
    assert tools["check_idea"].annotations.read_only_hint is True


def test_check_idea_rejects_too_short_text_without_an_api_call(fake_claude):
    check = call("check_idea", idea="ABC123")
    assert check["decision"] == "TOO_SHORT"
    assert check["hint"]
    assert fake_claude.requests == []


def test_check_idea_returns_the_gate_decision_in_words(fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    check = call("check_idea", idea="An app for dog owners")
    assert check["decision"] == "TOO_VAGUE"
    assert check["decision_text"] == "too vague to analyze"
    assert check["missing_information"] == ["target customer"]


def test_analyze_idea_returns_the_verdict_and_saves_the_report(fake_claude, results_dir):
    result = call("analyze_idea", idea=IDEA, name="Meal prep / Vilnius!")
    assert result["analyzed"] is True
    assert result["verdict"] == "Needs validation"
    assert result["verdict_code"] == "NEEDS_VALIDATION"
    assert "## Verdict: Needs validation" in result["report_markdown"]
    run_dir = next(results_dir.iterdir())
    assert run_dir.name.endswith("_meal_prep_vilnius")
    assert (run_dir / "report.md").exists()
    assert Path(result["report_json_path"]) == run_dir / "report.json"
    assert Path(result["report_json_path"]).exists()


def test_analyze_idea_stops_on_a_vague_idea_unless_asked(fake_claude, results_dir):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    stopped = call("analyze_idea", idea="An app for dog owners")
    assert stopped["analyzed"] is False and stopped["check"]["decision"] == "TOO_VAGUE"
    assert fake_claude.calls(EvaluatorResult) == []

    forced = call("analyze_idea", idea="An app for dog owners", analyze_if_vague=True)
    assert forced["analyzed"] is True
    assert "Input check" in forced["report_markdown"]


def test_reports_land_in_the_project_whatever_folder_the_client_runs_in(
    fake_claude, results_dir, tmp_path, monkeypatch
):
    elsewhere = tmp_path / "client_session"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = call("analyze_idea", idea=IDEA, name="meals")
    report = Path(result["report_path"])
    assert report.is_absolute()
    assert report.parent.parent == results_dir
    assert Path(result["report_json_path"]).is_absolute()
    assert not (elsewhere / "results").exists()
