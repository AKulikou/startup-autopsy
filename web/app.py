"""
The FastAPI application: one page and a small JSON API.

    GET  /                          the page (web/static/index.html)
    GET  /api/options               example ideas and translation languages
    POST /api/runs                  start an analysis (one at a time)
    GET  /api/runs/active           the run in progress, if any (to reattach after a reload)
    GET  /api/runs/{id}/events      progress as server-sent events, from the first event
    GET  /api/runs/{id}/result      the finished result, in words
    GET  /api/runs/{id}/files/{kind} downloads: report, json, translation

It is meant for this machine only (python -m web binds to 127.0.0.1); the host
and origin checks below also stop another website open in the same browser
from starting paid runs through it.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import DOMAIN_LENSES, ENABLED_LENSES, EXTRA_LENSES, LENS_SELECTION, WEB_SEARCH, WEB_SEARCH_LENSES
from core.idea_input import InvalidIdeaError, prepare_idea
from core.result_writer import run_name
from evaluators.lenses import select_lenses
from gate.idea_gate import NEXT_STEP_HINT
from web.examples import examples_for_page
from web.languages import NATIVE_NAMES, languages_for_page
from web.runs import BusyError, RunManager
from web.view import download_paths, run_view

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = ("127.0.0.1", "localhost")
MAX_IDEA_CHARS = 20_000
# How often the event stream looks for new events; a run takes minutes.
EVENT_POLL_S = 0.3

MEDIA_TYPES = {"report": "text/markdown; charset=utf-8", "json": "application/json",
               "translation": "text/markdown; charset=utf-8"}


def web_search_lenses() -> list[str]:
    """
    Names of the lenses that may search the web with the current .env settings: a
    lens searches only with WEB_SEARCH on, if it is a search lens and if it can run
    at all (a domain lens such as Legal Counsel runs only with LENS_SELECTION on).
    """
    if not WEB_SEARCH:
        return []
    keys = ENABLED_LENSES + EXTRA_LENSES + (DOMAIN_LENSES if LENS_SELECTION else ())
    return [lens.name for lens in select_lenses(keys) if lens.key in WEB_SEARCH_LENSES]


class RunRequest(BaseModel):
    idea: str = Field(max_length=MAX_IDEA_CHARS)
    language: str | None = Field(None, description="English name of the translation language, or none.")
    analyze_if_vague: bool = False


def create_app(results_dir: Path = ROOT / "results") -> FastAPI:
    app = FastAPI(title="Startup Autopsy", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(LOCAL_HOSTS))
    runs = RunManager(results_dir)

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next):
        """A browser sends Origin with a cross-site POST: refuse any that is not this page."""
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Requests from other sites are not accepted."}, status_code=403)
        return await call_next(request)

    def get_run(run_id: str):
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(404, "No such analysis (the server keeps only recent ones in memory).")
        return run

    @app.get("/", include_in_schema=False)
    def page():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/options")
    def options():
        # The lenses that may search the web, so the page says truthfully where the
        # facts in a report come from.
        return {"examples": examples_for_page(), "languages": languages_for_page(),
                "web_search_lenses": web_search_lenses()}

    @app.post("/api/runs", status_code=202)
    def start_run(body: RunRequest):
        if body.language is not None and body.language not in NATIVE_NAMES:
            raise HTTPException(422, f"Translation into {body.language} is not offered.")
        try:
            idea, _ = prepare_idea(body.idea)
        except InvalidIdeaError as e:
            message = "The idea is empty." if e.code == "EMPTY" else str(e)
            raise HTTPException(422, f"{message} {NEXT_STEP_HINT}") from None
        name = run_name(" ".join(idea.split()[:6]), "web_idea")
        try:
            run = runs.start(idea, name, body.language, body.analyze_if_vague)
        except BusyError as e:
            return JSONResponse(
                {"detail": "Another analysis is running. It takes about 3 minutes; "
                           "this page follows it.", "active_run_id": e.active_run_id},
                status_code=409,
            )
        return {"run_id": run.id}

    @app.get("/api/runs/active")
    def active_run():
        run = runs.get(runs.active_run_id) if runs.active_run_id else None
        if run is None:
            return {"run_id": None, "elapsed_s": None}
        return {"run_id": run.id, "elapsed_s": round((datetime.now() - run.started_at).total_seconds())}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str):
        run = get_run(run_id)

        async def stream():
            sent = 0
            while True:
                events, finished = run.events_since(sent)
                for event in events:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent += len(events)
                if finished:
                    return
                await asyncio.sleep(EVENT_POLL_S)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/result")
    def run_result(run_id: str):
        run = get_run(run_id)
        if not run.finished:
            raise HTTPException(409, "The analysis is still running.")
        return run_view(run)

    @app.get("/api/runs/{run_id}/files/{kind}")
    def run_file(run_id: str, kind: str):
        run = get_run(run_id)
        path = download_paths(run).get(kind) if run.finished else None
        if path is None:
            raise HTTPException(404, "This file is not available for this analysis.")
        return FileResponse(path, media_type=MEDIA_TYPES[kind],
                            filename=f"{path.parent.name}_{path.name}")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
