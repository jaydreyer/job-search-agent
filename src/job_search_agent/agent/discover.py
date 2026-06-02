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
    # AI Labs & Foundation Models
    "Anthropic", "OpenAI", "Cohere", "Mistral", "Hugging Face", "Perplexity",
    "Together AI", "Fireworks AI", "Anyscale", "Replicate", "Baseten",
    "Scale AI", "Lambda", "CoreWeave", "Modal",

    # AI Applications & Assistants
    "Glean", "Sierra", "Cresta", "Harvey", "Writer", "Contextual AI",
    "Hebbia", "Abridge", "Cognition",

    # Conversation, Knowledge & Support AI
    "Aisera", "Moveworks", "Forethought", "Espressive", "Guru", "Intercom",

    # Sales & Revenue Intelligence
    "Gong", "Outreach", "Salesloft", "Highspot", "Seismic",

    # Voice, Video & Creative AI
    "ElevenLabs", "Runway", "Synthesia", "AssemblyAI", "Deepgram", "Vapi",

    # Talent & HR AI
    "Eightfold AI", "Paradox",

    # API, Developer Tools & Portals
    "Kong", "ReadMe", "Stoplight", "Speakeasy", "Postman",
    "Vercel", "Netlify", "GitLab", "Docker", "Replit",
    "Sentry", "CircleCI", "Render", "Railway", "Sourcegraph",
    "Linear", "Retool", "Temporal", "LaunchDarkly", "Cortex", "Mux",
    "Knock", "WorkOS", "Clerk", "Stytch", "Resend", "Liveblocks",
    "HashiCorp", "Pulumi", "Neon", "Supabase",

    # Data, Analytics & BI
    "Databricks", "Snowflake", "Hex", "ThoughtSpot", "Domo",
    "Amplitude", "Mixpanel", "Monte Carlo", "dbt Labs",
    "Confluent", "Fivetran", "Airbyte", "ClickHouse", "Cribl",
    "Census", "Hightouch",

    # Vector Databases & ML Infra
    "Pinecone", "Weaviate", "Qdrant", "Chroma", "LanceDB",
    "MongoDB", "Elastic", "Redis",
    "Weights & Biases", "Comet", "Arize", "Galileo",
    "Nomic", "LlamaIndex", "Unstructured",
    "Tecton", "Dataiku", "DataRobot", "H2O.ai", "Domino Data Lab",

    # AI Governance & Observability
    "Robust Intelligence", "Credo AI", "Fiddler AI",

    # Workflow & Integration Automation
    "Zapier", "Workato", "Tray.io", "Make",

    # Enterprise SaaS (SE-heavy orgs)
    "Notion", "Airtable", "Asana", "Figma", "Miro",
    "Rippling", "Deel", "Gusto", "Navan", "Vanta", "Drata",
    "Samsara", "Checkr", "Twilio",

    # Fintech & Payments Infrastructure
    "Stripe", "Plaid", "Brex", "Ramp",
    "Mercury", "Modern Treasury", "Unit", "Pipe",

    # Security & Identity
    "Cloudflare", "Fastly", "Okta", "1Password",
    "Snyk", "Wiz", "Lacework", "Tailscale",
    "Doppler", "Teleport", "Chainguard", "Aembit",

    # Enterprise AI Platforms & Infrastructure
    "Palantir", "Instabase", "Datadog",
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
