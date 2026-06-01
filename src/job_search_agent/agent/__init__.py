"""Claude Managed Agents layer: server-side agent loop with host-side custom tools.

- `tools`       — custom-tool schemas + the host-side dispatcher (reuses sources/).
- `setup`       — one-time: create the environment + agent, store their IDs.
- `run_session` — per-run orchestrator: open a session, stream events, answer
                  custom-tool calls host-side, download the digest the agent writes.
"""
