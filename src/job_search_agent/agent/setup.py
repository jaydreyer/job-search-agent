"""One-time setup: create the managed agent + environment, store their IDs in .env.

Run once (re-run with --force to create a fresh agent, or --update to bump the
existing agent to a new version after editing the prompt/tools/resume).

    uv run jobsearch-agent-setup
"""

from __future__ import annotations

import argparse
import re

import anthropic

from ..config import ROOT, SearchConfig, Secrets, load_resume
from .prompt import build_system_prompt
from .tools import TOOL_SCHEMAS

ENV_FILE = ROOT / ".env"
AGENT_NAME = "Job Search Agent"
ENV_NAME = "job-search-env"


def _agent_tools() -> list[dict]:
    # Built-in toolset (need `write` to emit the digest) + our host-side custom tools.
    return [{"type": "agent_toolset_20260401"}, *TOOL_SCHEMAS]


def _build_agent_kwargs(config: SearchConfig, resume: str) -> dict:
    return dict(
        name=AGENT_NAME,
        model=config.agent_model,
        system=build_system_prompt(resume),
        tools=_agent_tools(),
    )


def _write_env(updates: dict[str, str]) -> None:
    """Idempotently upsert KEY=value lines into .env."""
    text = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    for key, value in updates.items():
        line = f"{key}={value}"
        if re.search(rf"(?m)^{key}=.*$", text):
            text = re.sub(rf"(?m)^{key}=.*$", line, text)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
    ENV_FILE.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/update the managed job-search agent.")
    parser.add_argument("--force", action="store_true", help="Create a new agent even if one exists.")
    parser.add_argument("--update", action="store_true", help="Bump the existing agent to a new version.")
    args = parser.parse_args()

    secrets = Secrets()
    config = SearchConfig.load()
    resume = load_resume()
    client = anthropic.Anthropic(api_key=secrets.anthropic_api_key or None)

    if args.update:
        if not secrets.agent_id:
            raise SystemExit("No AGENT_ID in .env — run without --update first.")
        current = client.beta.agents.retrieve(secrets.agent_id)
        agent = client.beta.agents.update(
            secrets.agent_id, version=current.version, **_build_agent_kwargs(config, resume)
        )
        print(f"Updated agent {agent.id} → version {agent.version}")
        return

    if secrets.agent_id and not args.force:
        raise SystemExit(
            f"Agent already exists ({secrets.agent_id}). "
            "Use --update to push prompt/tool changes, or --force for a brand-new agent."
        )

    env_id = secrets.environment_id
    if not env_id:
        environment = client.beta.environments.create(
            name=ENV_NAME,
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )
        env_id = environment.id
        print(f"Created environment {env_id}")

    agent = client.beta.agents.create(**_build_agent_kwargs(config, resume))
    print(f"Created agent {agent.id} (version {agent.version})")

    _write_env({"AGENT_ID": agent.id, "ENVIRONMENT_ID": env_id})
    print(f"Wrote AGENT_ID and ENVIRONMENT_ID to {ENV_FILE}")
    print("\nNext: uv run jobsearch-agent-run")


if __name__ == "__main__":
    main()
