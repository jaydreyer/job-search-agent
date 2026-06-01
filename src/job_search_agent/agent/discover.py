"""Discover live ATS boards from a big list of company names.

For each company it probes Greenhouse, Lever, and Ashby with a normalized slug
and keeps whichever provider returns live postings — so you don't need to know
each company's ATS in advance. Writes the verified set to config/ats_boards.yaml,
which SearchConfig loads automatically.

    uv run jobsearch-validate-boards            # use built-in company list
    uv run jobsearch-validate-boards --names config/companies.txt
"""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import yaml

from ..config import ROOT, AtsBoard
from ..sources.ats.ashby import fetch_ashby
from ..sources.ats.greenhouse import fetch_greenhouse
from ..sources.ats.lever import fetch_lever

OUT_FILE = ROOT / "config" / "ats_boards.yaml"
PROVIDERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}

# Slugs that aren't just the normalized company name.
OVERRIDES = {
    "Weights & Biases": "wandb",
    "dbt Labs": "dbtlabs",
    "Hugging Face": "huggingface",
}

# Broad seed list, weighted toward companies that hire Solutions Engineers,
# Forward Deployed Engineers, DevRel, and AI product roles. Many will not resolve
# (wrong ATS / private board) — the probe keeps only the live ones.
COMPANIES = [
    # AI labs / products
    "OpenAI", "Anthropic", "Cohere", "Mistral", "Hugging Face", "Perplexity", "Scale AI",
    "Runway", "ElevenLabs", "Character AI", "Together AI", "Fireworks AI", "Anyscale",
    "Replicate", "Stability AI", "Adept", "Contextual AI", "Glean", "Sierra", "Cresta",
    "Harvey", "Cohere", "Writer", "Jasper", "Synthesia", "AssemblyAI", "Deepgram",
    "LanceDB", "Baseten", "Modal", "Lambda", "CoreWeave", "Hebbia", "Abridge", "Cognition",
    # Dev tools / infra
    "Vercel", "Netlify", "GitLab", "HashiCorp", "Docker", "Replit", "Postman", "Sentry",
    "CircleCI", "Render", "Railway", "Supabase", "PlanetScale", "Neon", "Pulumi", "Grafana",
    "Sourcegraph", "Linear", "Retool", "Temporal", "LaunchDarkly", "Cortex", "Mux",
    "Vapi", "Knock", "WorkOS", "Clerk", "Stytch", "Speakeasy", "Resend", "Liveblocks",
    # Data / ML infra
    "Databricks", "Snowflake", "Confluent", "Fivetran", "Airbyte", "Pinecone", "Weaviate",
    "Qdrant", "MongoDB", "Elastic", "Redis", "ClickHouse", "Datadog", "Cribl", "Monte Carlo",
    "dbt Labs", "Hex", "Census", "Hightouch", "Tecton", "Weights & Biases", "Comet",
    "Arize", "Galileo", "Nomic", "LlamaIndex", "Unstructured", "Chroma",
    # Fintech / enterprise SaaS (heavy SE / solutions)
    "Stripe", "Plaid", "Brex", "Ramp", "Twilio", "Notion", "Airtable", "Asana", "Figma",
    "Miro", "Amplitude", "Mixpanel", "Zapier", "Workato", "Gusto", "Rippling", "Deel",
    "Checkr", "Samsara", "Mercury", "Modern Treasury", "Unit", "Pipe", "Navan", "Vanta",
    "Drata", "Census", "Census",
    # Security / cloud / identity
    "Cloudflare", "Fastly", "Okta", "1Password", "Snyk", "Wiz", "Lacework", "Tailscale",
    "Doppler", "Teleport", "Chainguard", "Aembit",
    # AI-forward enterprise / platforms
    "Palantir", "Instabase", "Moveworks", "Dataiku", "DataRobot", "H2O.ai", "Domino Data Lab",
    "Tecton", "Robust Intelligence", "Credo AI", "Fiddler AI",
    # Match Group is known-good (keep it for continuity)
    "Match Group",
]


def _slug(name: str) -> str:
    return OVERRIDES.get(name, re.sub(r"[^a-z0-9]", "", name.lower()))


def _probe(name: str) -> dict | None:
    slug = _slug(name)
    with httpx.Client(timeout=12, follow_redirects=True) as client:
        for provider, fetch in PROVIDERS.items():
            try:
                postings = fetch(client, AtsBoard(provider=provider, slug=slug, label=name))
            except Exception:  # noqa: BLE001 - 404 / wrong provider
                continue
            if postings:
                return {"provider": provider, "slug": slug, "label": name, "count": len(postings)}
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover live ATS boards from company names.")
    parser.add_argument("--names", type=Path, help="Newline-separated company-name file.")
    args = parser.parse_args()

    names = COMPANIES
    if args.names:
        names = [ln.strip() for ln in args.names.read_text().splitlines() if ln.strip()]
    names = list(dict.fromkeys(names))  # dedupe, keep order

    print(f"Probing {len(names)} companies across greenhouse/lever/ashby…")
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for result in pool.map(_probe, names):
            if result:
                found.append(result)
                print(f"  ✓ {result['label']:24} {result['provider']}:{result['slug']} ({result['count']} jobs)")

    found.sort(key=lambda r: r["count"], reverse=True)
    boards = [{"provider": r["provider"], "slug": r["slug"], "label": r["label"]} for r in found]
    OUT_FILE.write_text(yaml.safe_dump({"ats_boards": boards}, sort_keys=False))

    total_jobs = sum(r["count"] for r in found)
    print(
        f"\nVerified {len(found)}/{len(names)} companies "
        f"({total_jobs} total open postings) → {OUT_FILE}"
    )


if __name__ == "__main__":
    main()
