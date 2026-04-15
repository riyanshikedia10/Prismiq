"""
Prismiq — Central configuration.
Validates environment on import, sets up logging, provides typed settings.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

from models import ConfigError

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for the entire application."""
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=level)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


# ── Settings ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Settings:
    """Typed, validated application settings loaded from environment."""
    openai_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    kaggle_username: str = ""
    kaggle_key: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ConfigError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill in your key."
            )
        return cls(
            openai_api_key=api_key,
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
            kaggle_username=os.getenv("KAGGLE_USERNAME", ""),
            kaggle_key=os.getenv("KAGGLE_KEY", ""),
        )


def get_settings() -> Settings:
    """Singleton-ish accessor; re-reads env each call (safe for tests)."""
    return Settings.from_env()


# ── Role & Company Constants ─────────────────────────────────────────────────

ROLES: list[str] = ["Data Scientist", "Data Engineer", "Data Analyst"]

ROLE_SLUGS: dict[str, str] = {
    "Data Scientist": "ds",
    "Data Engineer": "de",
    "Data Analyst": "da",
}

EXPERIENCE_LEVELS: list[str] = ["Entry", "Mid", "Senior"]

COMPANIES: list[str] = [
    "Google", "Amazon", "Meta", "Apple", "Netflix",
    "Microsoft", "Tesla", "TikTok", "Uber",
]

# ── External Data Source Mappings ────────────────────────────────────────────

GITHUB_LEETCODE_BASE: str = (
    "https://raw.githubusercontent.com/krishnadey30/"
    "LeetCode-Questions-CompanyWise/master"
)

LEETCODE_CSV_MAP: dict[str, str | None] = {
    "Google": "google_alltime.csv",
    "Amazon": "amazon_alltime.csv",
    "Meta": "facebook_alltime.csv",
    "Apple": "apple_alltime.csv",
    "Netflix": None,
    "Microsoft": "microsoft_alltime.csv",
    "Tesla": None,
    "TikTok": None,
    "Uber": "uber_alltime.csv",
}

KAGGLE_DATASET: str = "asaniczka/data-science-job-postings-and-skills"

COMPANY_ALIASES: dict[str, list[str]] = {
    "Google": ["google", "alphabet"],
    "Amazon": ["amazon", "aws"],
    "Meta": ["meta", "facebook"],
    "Apple": ["apple"],
    "Netflix": ["netflix"],
    "Microsoft": ["microsoft"],
    "Tesla": ["tesla"],
    "TikTok": ["tiktok", "bytedance"],
    "Uber": ["uber"],
}

JOB_TITLE_KEYWORDS: dict[str, list[str]] = {
    "Data Scientist": [
        "data scientist", "machine learning engineer", "ml engineer",
        "research scientist", "applied scientist",
    ],
    "Data Engineer": [
        "data engineer", "analytics engineer", "etl developer",
        "data platform engineer", "big data engineer", "pipeline engineer",
    ],
    "Data Analyst": [
        "data analyst", "business analyst", "analytics analyst",
        "reporting analyst", "bi analyst", "business intelligence analyst",
    ],
}

LEETCODE_DIFFICULTY_FILTER: dict[str, list[str]] = {
    "Data Scientist": ["Easy", "Medium", "Hard"],
    "Data Engineer": ["Easy", "Medium", "Hard"],
    "Data Analyst": ["Easy", "Medium"],
}

SQL_KEYWORDS: list[str] = [
    "sql", "database", "table", "query", "select", "join",
    "department", "employee", "salary", "manager", "customer",
    "duplicate", "consecutive", "rank", "nth", "second highest",
]

# ── UI Constants ─────────────────────────────────────────────────────────────

COMPANY_COLORS: dict[str, str] = {
    "Google": "#4285F4", "Amazon": "#FF9900", "Meta": "#0668E1",
    "Apple": "#555555", "Netflix": "#E50914", "Microsoft": "#00A4EF",
    "Tesla": "#CC0000", "TikTok": "#010101", "Uber": "#000000",
}

