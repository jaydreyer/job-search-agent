"""Per-run orchestrator. Opens a session against the pre-created agent, streams
events, executes custom-tool calls host-side, and downloads the digest the agent
writes to /mnt/session/outputs/.

    uv run jobsearch-agent-run
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import anthropic

from .. import feedback
from ..config import ROOT, SearchConfig, Secrets
from .prompt import build_kickoff
from .tools import handle_custom_tool

OUT_DIR = ROOT / "data" / "digests"
MANAGED_BETA = "managed-agents-2026-04-01"


def _require(secrets: Secrets) -> None:
    missing = [
        name
        for name, val in [("AGENT_ID", secrets.agent_id), ("ENVIRONMENT_ID", secrets.environment_id)]
        if not val
    ]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)} in .env — run `uv run jobsearch-agent-setup` first.")


def _drain(client: anthropic.Anthropic, session_id: str, kickoff: str) -> None:
    """Single persistent stream: print agent text, answer custom tools inline,
    stop when the session is idle with nothing pending (or terminated).

    Keeping ONE stream open avoids the SSE no-replay gap — if we reopened the
    stream after each tool batch, events the agent emits in between (scoring,
    file writes) would be lost.
    """
    pending: list = []

    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        # stream-first: stream is open, now send the kickoff.
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": kickoff}]}],
        )

        for event in stream:
            t = event.type
            if t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        print(block.text, end="", flush=True)
            elif t == "agent.tool_use":  # built-in tool (e.g. write) — visibility only
                print(f"\n  · {getattr(event, 'name', 'tool')}", flush=True)
            elif t == "agent.custom_tool_use":
                print(f"\n  → tool: {event.name}({event.input})", flush=True)
                pending.append(event)
            elif t == "session.status_terminated":
                return
            elif t == "session.status_idle":
                # Each tool call emits its own requires_action idle. Only a
                # terminal stop_reason (end_turn / retries_exhausted) means done —
                # requires_action means the agent is still waiting on us.
                reason = getattr(getattr(event, "stop_reason", None), "type", None)
                if reason and reason != "requires_action":
                    return
                if pending:
                    results = [
                        {
                            "type": "user.custom_tool_result",
                            "custom_tool_use_id": call.id,
                            "content": [
                                {"type": "text", "text": handle_custom_tool(call.name, dict(call.input))}
                            ],
                        }
                        for call in pending
                    ]
                    pending = []
                    client.beta.sessions.events.send(session_id=session_id, events=results)
                # keep iterating the SAME stream — no gap


def _download_outputs(client: anthropic.Anthropic, session_id: str) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    saved: list[Path] = []
    for attempt in range(4):  # brief indexing lag after idle
        files = list(client.beta.files.list(scope_id=session_id, betas=[MANAGED_BETA]))
        if files:
            for f in files:
                dest = OUT_DIR / f"{stamp}-{f.filename}"
                client.beta.files.download(f.id).write_to_file(dest)
                saved.append(dest)
            break
        time.sleep(2)
    return saved


def main() -> None:
    secrets = Secrets()
    _require(secrets)
    config = SearchConfig.load()
    client = anthropic.Anthropic(api_key=secrets.anthropic_api_key or None)

    session = client.beta.sessions.create(
        agent=secrets.agent_id,
        environment_id=secrets.environment_id,
        title=f"Job search {date.today().isoformat()}",
    )
    print(f"Session {session.id}")
    print(f"Watch in Console: https://platform.claude.com/workspaces/default/sessions/{session.id}\n")

    _drain(client, session.id, build_kickoff(config, feedback.preferences()))

    saved = _download_outputs(client, session.id)
    if saved:
        print("\n\nDigest saved:")
        for p in saved:
            print(f"  {p}")
        from ..web.dashboard import build_dashboard

        dash = build_dashboard()
        print(f"\nDashboard updated: file://{dash}")
    else:
        print("\n\nNo output files found — check the session in Console.")


if __name__ == "__main__":
    main()
