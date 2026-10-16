"""The web UI's API, end to end through FastAPI's test client, with a fake Claude."""

import json
import threading

import pytest
from conftest import gate_result, lens_result, response, synthesis_result
from fastapi.testclient import TestClient

from config import ENABLED_LENSES
from evaluators.lenses import select_lenses
from evaluators.schemas import EvaluatorResult, Verdict
from gate.schemas import GateDecision, GateResult
from synthesis.schemas import SynthesisResult
from web import examples as examples_module
from web.app import create_app

IDEA = "Weekly meal-prep delivery for office workers in Vilnius, 60 EUR a week, ordered online."
LENSES = select_lenses(ENABLED_LENSES)
BASE_URL = "http://127.0.0.1:8000"
CODES = {v.value for v in Verdict} | {d.value for d in GateDecision}
# Fields that hold codes for the page's logic and styling, never shown as text.
CODE_FIELDS = {"verdict", "decision", "key", "kind"}


@pytest.fixture
def results_dir(tmp_path):
    return tmp_path / "results"


@pytest.fixture
def client(results_dir):
    with TestClient(create_app(results_dir), base_url=BASE_URL) as test_client:
        yield test_client


def start(client, idea=IDEA, **options) -> str:
    reply = client.post("/api/runs", json={"idea": idea, **options})
    assert reply.status_code == 202, reply.text
    return reply.json()["run_id"]


def follow(client, run_id) -> list[dict]:
    """Read the event stream to its end, as the page does."""
    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def run_to_end(client, idea=IDEA, **options) -> tuple[str, list[dict], dict]:
    run_id = start(client, idea, **options)
    events = follow(client, run_id)
    result = client.get(f"/api/runs/{run_id}/result")
    assert result.status_code == 200
    return run_id, events, result.json()


def shown_texts(value, field=None):
    """Every string in the result view that the page may show to a person."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from shown_texts(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from shown_texts(item, field)
    elif isinstance(value, str) and field not in CODE_FIELDS:
        yield value


def test_the_page_and_its_scripts_are_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "<title>Startup Autopsy</title>" in page.text
    for asset in ("app.js", "events.js", "cards.js", "languages.js", "markdown.js", "tokens.css", "app.css"):
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_options_offer_the_agreed_examples_and_languages(client):
    options = client.get("/api/options").json()
    assert len(options["examples"]) == 5
    assert all(example["text"].strip() for example in options["examples"])
    labels = [language["label"] for language in options["languages"]]
    # The default first, then alphabetical by the languages' own names; no English.
    assert labels == ["Lietuvių", "Deutsch", "Eesti", "Español", "Français", "Italiano",
                      "Latviešu", "Polski", "Русский", "Українська"]
    assert "English" not in [language["name"] for language in options["languages"]]
    # The footer says where the facts come from; .env decides (WEB_SEARCH, LENS_SELECTION).
    assert isinstance(options["web_search_lenses"], list)


@pytest.mark.parametrize(
    "web_search, lens_selection, expected",
    [
        (False, True, []),
        (True, False, ["Reality Auditor"]),  # Legal Counsel is a domain lens: it does not run
        (True, True, ["Reality Auditor", "Legal Counsel"]),
    ],
)
def test_the_footer_names_only_the_lenses_that_can_search(monkeypatch, web_search, lens_selection, expected):
    from web import app as app_module
    monkeypatch.setattr(app_module, "WEB_SEARCH", web_search)
    monkeypatch.setattr(app_module, "LENS_SELECTION", lens_selection)
    monkeypatch.setattr(app_module, "EXTRA_LENSES", ())
    assert app_module.web_search_lenses() == expected


def test_examples_never_come_from_personal_ideas():
    for example in examples_module.EXAMPLES:
        assert example.source is None or "private" not in example.source


def test_the_one_line_example_passes_the_local_check():
    from core.idea_input import prepare_idea
    one_liner = next(e for e in examples_module.EXAMPLES if e.text)
    prepare_idea(one_liner.text)  # raises if too short to reach the input check


def test_too_short_text_is_rejected_before_any_api_call(client, fake_claude):
    reply = client.post("/api/runs", json={"idea": "A gym"})
    assert reply.status_code == 422
    assert "Too short to analyze" in reply.json()["detail"]
    assert fake_claude.requests == []


def test_a_language_outside_the_list_is_refused(client, fake_claude):
    reply = client.post("/api/runs", json={"idea": IDEA, "language": "Klingon"})
    assert reply.status_code == 422
    assert fake_claude.requests == []


def test_a_full_run_streams_progress_and_ends_with_the_result_in_words(client, fake_claude, results_dir):
    run_id, events, result = run_to_end(client)
    assert events[0]["stage"] == "input_check"
    lens_done = [e for e in events if e["stage"] == "lens" and e["status"] == "done"]
    assert [e["key"] for e in lens_done] != [] and len(lens_done) == len(LENSES)
    assert events[-1]["stage"] == "run" and events[-1]["status"] == "done"

    assert result["analyzed"] is True
    assert result["synthesis"]["verdict_text"] == "Needs validation"
    assert result["synthesis"]["confidence_text"] == "Medium"
    assert [lens["name"] for lens in result["lenses"]] == [lens.name for lens in LENSES]
    assert all(lens["focus"] for lens in result["lenses"])
    leaked = [text for text in shown_texts(result) if any(code in text for code in CODES)]
    assert leaked == []
    run_dir = next(results_dir.iterdir())
    assert run_dir.name.endswith("_weekly_meal_prep_delivery_for_office_workers")


def test_the_run_cost_is_the_sum_of_its_calls(client, fake_claude):
    _, events, result = run_to_end(client)
    calls = sum(e["cost_usd"] or 0 for e in events if e["stage"] != "run")
    assert result["cost_usd"] > 0
    assert result["cost_usd"] == pytest.approx(calls, abs=1e-4)
    assert events[-1]["cost_usd"] == pytest.approx(calls)


def test_reports_can_be_downloaded(client, fake_claude):
    run_id, _, result = run_to_end(client)
    assert [d["kind"] for d in result["downloads"]] == ["report"]
    report = client.get(f"/api/runs/{run_id}/files/report")
    assert report.status_code == 200 and "## Verdict: Needs validation" in report.text
    assert "attachment" in report.headers["content-disposition"]
    # report.json is still written for programs (MCP), but the page does not offer it.
    assert client.get(f"/api/runs/{run_id}/files/json").status_code == 404
    assert client.get(f"/api/runs/{run_id}/files/translation").status_code == 404
    assert client.get(f"/api/runs/{run_id}/files/..%2F..%2Fconfig.py").status_code == 404


def test_without_the_checkbox_nothing_is_translated_whatever_env_says(client, fake_claude, monkeypatch):
    from core import analysis_runner
    monkeypatch.setattr(analysis_runner, "REPORT_TRANSLATION", "Lithuanian")
    _, events, result = run_to_end(client)
    assert result["translation"] is None
    assert not [e for e in events if e["stage"] == "translation"]


def test_a_requested_translation_is_made_marked_and_offered(client, fake_claude):
    run_id, events, result = run_to_end(client, language="Lithuanian")
    assert [e["status"] for e in events if e["stage"] == "translation"] == ["started", "done"]
    assert result["translation"] == {"language": "Lithuanian", "native_name": "Lietuvių",
                                     "made": True, "text": None}
    labels = {d["kind"]: d["label"] for d in result["downloads"]}
    # English page, English words: the language's own name never mixes into a sentence.
    assert labels == {"report": "Save report (report.md)",
                      "translation": "Save translation (report.lithuanian.md)"}
    translated = client.get(f"/api/runs/{run_id}/files/translation").text
    assert translated.startswith("> Machine translation into Lithuanian of the English original")


def test_the_page_can_show_the_translation_it_offers(client, fake_claude):
    """The page loads the translated copy to show it; the same URL also saves it."""
    run_id, _, _ = run_to_end(client, language="Russian")
    shown = client.get(f"/api/runs/{run_id}/files/translation")
    assert shown.status_code == 200
    assert shown.headers["content-type"].startswith("text/markdown")
    assert shown.text.startswith("> Machine translation into Russian of the English original")


def test_a_failed_translation_is_said_and_the_english_report_stays(client, fake_claude):
    def fails(kwargs):
        raise ConnectionError("Connection error.")

    fake_claude.create_handler = fails
    _, events, result = run_to_end(client, language="German")
    assert [e["status"] for e in events if e["stage"] == "translation"] == ["started", "failed"]
    assert result["translation"]["made"] is False
    assert [d["kind"] for d in result["downloads"]] == ["report"]


def test_a_vague_idea_comes_back_with_what_is_missing(client, fake_claude):
    fake_claude.handlers[GateResult] = lambda kw: response(gate_result("TOO_VAGUE"))
    _, _, result = run_to_end(client, idea="An app for fitness fans")
    assert result["analyzed"] is False
    check = result["input_check"]
    assert (check["decision"], check["text"]) == ("TOO_VAGUE", "too vague to analyze")
    assert check["missing"] == ["target customer"] and check["hint"]
    assert fake_claude.calls(EvaluatorResult) == []

    _, _, forced = run_to_end(client, idea="An app for fitness fans", analyze_if_vague=True)
    assert forced["analyzed"] is True
    assert "too vague" in forced["input_note"]


def test_a_failed_lens_shows_as_a_failed_card_and_the_verdict_still_comes(client, fake_claude):
    first = LENSES[0]

    def one_fails(kwargs):
        if first.role in kwargs["system"]:
            raise ConnectionError("Connection error.")
        return response(lens_result())

    fake_claude.handlers[EvaluatorResult] = one_fails
    _, events, result = run_to_end(client)
    assert [e["key"] for e in events if e["stage"] == "lens" and e["status"] == "failed"] == [first.key]
    failed = result["lenses"][0]
    assert failed["ok"] is False and "failed" in failed["text"]
    assert result["synthesis"]["ok"] is True


def test_only_one_run_at_a_time(client, fake_claude):
    release = threading.Event()

    def slow_gate(kwargs):
        release.wait(timeout=10)
        return response(gate_result())

    fake_claude.handlers[GateResult] = slow_gate
    first = start(client)
    second = client.post("/api/runs", json={"idea": IDEA})
    assert second.status_code == 409
    assert second.json()["active_run_id"] == first
    assert client.get("/api/runs/active").json()["run_id"] == first
    assert client.get(f"/api/runs/{first}/result").status_code == 409  # still running

    release.set()
    follow(client, first)
    assert client.get("/api/runs/active").json()["run_id"] is None
    # Free again. Follow the new run to its end: a run left in its thread would outlive
    # the fake client and reach the real API after the test.
    follow(client, start(client))


def test_requests_from_another_site_are_refused(client, fake_claude):
    reply = client.post("/api/runs", json={"idea": IDEA}, headers={"Origin": "https://evil.example"})
    assert reply.status_code == 403
    assert fake_claude.requests == []
    same = client.post("/api/runs", json={"idea": IDEA}, headers={"Origin": BASE_URL})
    assert same.status_code == 202


def test_only_local_host_names_are_served(results_dir):
    with TestClient(create_app(results_dir), base_url="http://attacker.example") as other:
        assert other.get("/api/options").status_code == 400


def test_an_unknown_run_is_not_found(client):
    assert client.get("/api/runs/nope/result").status_code == 404
    assert client.get("/api/runs/nope/events").status_code == 404


def test_codes_the_models_write_into_their_text_are_shown_as_words(client, fake_claude, results_dir):
    fake_claude.handlers[SynthesisResult] = lambda kw: response(synthesis_result(
        summary="This is clearly VIABLE_IF, not NOT_VIABLE: the deciding question is still open.",
        confidence_reason="Confidence is MEDIUM because demand is untested.",
    ))
    fake_claude.handlers[EvaluatorResult] = lambda kw: response(lens_result(
        summary="A HIGH confidence VIABLE verdict: the build is simple and the tools are proven.",
    ))
    _, _, result = run_to_end(client)
    leaked = [text for text in shown_texts(result) if any(code in text for code in CODES)]
    assert leaked == []
    assert result["synthesis"]["summary"].startswith(
        "This is clearly 'viable if conditions hold', not 'not viable'")
    assert result["synthesis"]["verdict"] == "NEEDS_VALIDATION"  # codes stay for the page's logic
    report = (next(results_dir.iterdir()) / "report.md").read_text(encoding="utf-8")
    assert "VIABLE_IF" not in report and "'not viable'" in report
