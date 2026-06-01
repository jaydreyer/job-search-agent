"""Tiny local server for the interactive dashboard.

Serves the dashboard at http://localhost:8137 and persists Applied /
Not-interested / ⭐ clicks and preferences to data/feedback.json. Same-origin,
so no CORS and nothing leaves your machine.

    uv run jobsearch-serve
"""

from __future__ import annotations

import threading
import webbrowser

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .. import feedback
from .dashboard import build_dashboard

PORT = 8137
app = FastAPI(title="Job Search Dashboard")


class FeedbackIn(BaseModel):
    company: str
    title: str
    status: str  # applied | dismissed | starred | clear


class PreferenceIn(BaseModel):
    text: str
    action: str  # add | remove


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    # Rebuild on each load so it reflects the latest digests + feedback.
    return build_dashboard().read_text()


@app.get("/api/state")
def state() -> JSONResponse:
    return JSONResponse({"items": feedback.items(), "preferences": feedback.preferences()})


@app.post("/api/feedback")
def set_feedback(fb: FeedbackIn) -> JSONResponse:
    feedback.set_status(fb.company, fb.title, fb.status)
    return JSONResponse({"ok": True})


@app.post("/api/preference")
def set_preference(p: PreferenceIn) -> JSONResponse:
    if p.action == "add":
        feedback.add_preference(p.text)
    elif p.action == "remove":
        feedback.remove_preference(p.text)
    return JSONResponse({"ok": True, "preferences": feedback.preferences()})


def main() -> None:
    url = f"http://localhost:{PORT}"
    print(f"Dashboard: {url}  (Ctrl-C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
