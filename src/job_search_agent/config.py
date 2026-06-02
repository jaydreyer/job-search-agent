"""Configuration: secrets from environment, search parameters from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

ROOT = Path(__file__).resolve().parents[2]


class Secrets(BaseSettings):
    """Loaded from environment / .env. Never commit real values."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        # .env is the source of truth for this tool, so it wins over process env
        # vars — some shells inject an empty ANTHROPIC_API_KEY="" that would
        # otherwise shadow the real key in .env.
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    anthropic_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    # Populated by `jobsearch-agent-setup` (managed agent + environment IDs).
    agent_id: str = ""
    environment_id: str = ""


class AtsBoard(BaseModel):
    """A single company's ATS board to poll."""

    provider: str  # "greenhouse" | "lever" | "ashby"
    slug: str  # company token in the ATS url, e.g. "stripe"
    label: str | None = None  # human-friendly name override


class SearchQuery(BaseModel):
    keywords: str
    location: str | None = None
    remote_only: bool = False


class SearchConfig(BaseModel):
    """What to search for — edit config/search_config.yaml to change."""

    queries: list[SearchQuery] = Field(default_factory=list)
    ats_boards: list[AtsBoard] = Field(default_factory=list)
    country: str = "us"  # adzuna country code
    results_per_query: int = 50
    min_score_for_digest: int = 70
    scoring_model: str = "claude-sonnet-4-6"  # local-pipeline per-posting scoring
    agent_model: str = "claude-opus-4-8"  # managed-agent model (does tool use + scoring)
    # Specific role-title phrases used to pre-filter big company boards. Kept tight
    # on purpose — broad words like "engineer" match thousands of irrelevant rows.
    role_keywords: list[str] = Field(
        default_factory=lambda: [
            "solutions engineer", "solutions architect", "forward deployed", "sales engineer",
            "developer advocate", "developer relations", "devrel", "developer experience",
            "customer engineer", "field engineer", "field cto", "ai engineer", "ml engineer",
            "machine learning engineer", "applied ai", "applied machine learning",
            "ai solutions", "genai", "ai product manager", "technical product manager",
            "ai enablement", "developer enablement", "evangelist", "ai architect",
        ]
    )

    @classmethod
    def load(cls, path: Path | None = None) -> "SearchConfig":
        path = path or ROOT / "config" / "search_config.yaml"
        data = yaml.safe_load(path.read_text()) or {}
        # A large verified board list lives in its own file so the validator can
        # rewrite it without touching the hand-edited search config.
        boards_path = ROOT / "config" / "ats_boards.yaml"
        if boards_path.exists():
            bdata = yaml.safe_load(boards_path.read_text()) or {}
            if bdata.get("ats_boards"):
                data["ats_boards"] = bdata["ats_boards"]
        # Hand-maintained boards the auto-validator can't discover (Workday/Workable).
        extra_path = ROOT / "config" / "extra_boards.yaml"
        if extra_path.exists():
            edata = yaml.safe_load(extra_path.read_text()) or {}
            data.setdefault("ats_boards", [])
            data["ats_boards"] = list(data["ats_boards"]) + list(edata.get("ats_boards", []))
        return cls.model_validate(data)


def load_resume(path: Path | None = None) -> str:
    path = path or ROOT / "data" / "resume.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Resume not found at {path}. Paste your resume (markdown or plain text) there."
        )
    text = path.read_text().strip()
    if not text:
        raise ValueError(f"Resume file {path} is empty.")
    return text
