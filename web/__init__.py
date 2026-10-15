"""
Minimal local web UI for Startup Autopsy (design: docs/web_ui.md).

Run with `python -m web` and open http://127.0.0.1:8000. FastAPI serves one
page (web/static/) and a small JSON API; progress reaches the page as
server-sent events built from core.progress.ProgressEvent.
"""
