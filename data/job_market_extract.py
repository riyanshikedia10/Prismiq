"""
Extract company-role-skill mappings from multiple Kaggle job market datasets.

Sources:
  1. asaniczka/data-science-job-postings-and-skills (12K records, skills column)
  2. elahehgolrokh/data-science-job-postings-with-salaries-2025 (skills + company)

Outputs:
  data/processed/job_market_skills.json — skills per role with frequencies
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from pathlib import Path

from config import COMPANY_ALIASES, ROLES, COMPANIES, setup_logging

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "processed"

DATASETS = [
    "asaniczka/data-science-job-postings-and-skills",
    "elahehgolrokh/data-science-job-postings-with-salaries-2025",
]

ROLE_KEYWORDS: dict[str, list[str]] = {
    "Data Scientist": ["data scientist", "machine learning", "ml engineer", "research scientist", "applied scientist"],
    "Data Engineer": ["data engineer", "analytics engineer", "etl", "pipeline engineer", "big data engineer", "data platform"],
    "Data Analyst": ["data analyst", "business analyst", "bi analyst", "business intelligence", "analytics analyst", "reporting analyst"],
}


def _match_company(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    lower = name.lower().strip()
    for company, aliases in COMPANY_ALIASES.items():
        if any(a in lower for a in aliases):
            return company
    return None


def _match_role(title: str) -> str | None:
    if not isinstance(title, str):
        return None
    lower = title.lower().strip()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return role
    return None


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        for col in df.columns:
            if c in col.lower():
                return col
    return None


def _parse_skills(raw: str) -> list[str]:
    """Split a skills string into individual skill names."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    skills = re.split(r"[,;|/]", raw)
    return [s.strip() for s in skills if s.strip() and len(s.strip()) > 1]


def _process_dataset(dataset_id: str) -> list[dict]:
    """Download and extract skills from a single Kaggle dataset."""
    try:
        import kagglehub
    except ImportError:
        logger.error("kagglehub not installed")
        return []

    logger.info("Downloading %s...", dataset_id)
    try:
        path = kagglehub.dataset_download(dataset_id)
    except Exception as exc:
        logger.warning("Download failed for %s: %s", dataset_id, exc)
        return []

    # Find all CSVs
    csv_files = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".csv"):
                csv_files.append(os.path.join(root, f))

    if not csv_files:
        logger.warning("No CSV files in %s", path)
        return []

    all_records: list[dict] = []

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        logger.info("  %s: %d rows", os.path.basename(csv_path), len(df))

        title_col = _find_col(df, ["job_title", "title", "job_name"])
        company_col = _find_col(df, ["company", "company_name"])
        skills_col = _find_col(df, ["skill", "job_skill"])

        if not title_col:
            logger.warning("  No title column, skipping")
            continue

        # If skills are in a separate file (asaniczka pattern), try joining
        if not skills_col:
            join_col = _find_col(df, ["job_link", "job_id"])
            if join_col:
                for other_csv in csv_files:
                    if other_csv == csv_path:
                        continue
                    other_df = pd.read_csv(other_csv)
                    if join_col in other_df.columns:
                        sk_col = _find_col(other_df, ["skill", "job_skill"])
                        if sk_col:
                            df = df.merge(other_df[[join_col, sk_col]], on=join_col, how="left")
                            skills_col = sk_col
                            logger.info("  Joined skills from %s", os.path.basename(other_csv))
                            break

        if not skills_col:
            logger.warning("  No skills column found")
            continue

        df["_role"] = df[title_col].apply(_match_role)
        if company_col:
            df["_company"] = df[company_col].apply(_match_company)
        else:
            df["_company"] = None

        matched = df[df["_role"].notna()]
        logger.info("  Role-matched: %d / %d", len(matched), len(df))

        for _, row in matched.iterrows():
            role = row["_role"]
            company = row.get("_company") or "General"
            raw_skills = row.get(skills_col, "")
            for skill in _parse_skills(str(raw_skills)):
                all_records.append({
                    "skill": skill,
                    "role": role,
                    "company": company,
                    "source": f"kaggle:{dataset_id}",
                })

    return all_records


def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    for ds in DATASETS:
        records = _process_dataset(ds)
        all_records.extend(records)
        logger.info("  -> %d skill records from %s", len(records), ds)

    logger.info("Total raw skill records: %d", len(all_records))

    # Aggregate by role
    result: dict[str, list[dict]] = {}
    for role in ROLES:
        role_records = [r for r in all_records if r["role"] == role]
        freq: dict[str, int] = {}
        company_freq: dict[str, dict[str, int]] = {}

        for r in role_records:
            name = r["skill"]
            freq[name] = freq.get(name, 0) + 1
            co = r["company"]
            if co not in company_freq:
                company_freq[co] = {}
            company_freq[co][name] = company_freq[co].get(name, 0) + 1

        sorted_skills = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        skills_list = []
        for rank, (name, count) in enumerate(sorted_skills):
            if rank < len(sorted_skills) * 0.2:
                importance = "Critical"
            elif rank < len(sorted_skills) * 0.5:
                importance = "High"
            else:
                importance = "Medium"
            # Find which companies need this skill
            companies_needing = [
                co for co, sk_freq in company_freq.items()
                if name in sk_freq and co != "General"
            ]
            skills_list.append({
                "name": name,
                "importance": importance,
                "frequency": count,
                "companies": companies_needing,
                "source": "kaggle",
            })

        result[role] = skills_list
        logger.info("[%s] %d unique skills", role, len(skills_list))

    outpath = OUTPUT_DIR / "job_market_skills.json"
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2)

    total = sum(len(v) for v in result.values())
    logger.info("Saved %d skills -> %s", total, outpath)


if __name__ == "__main__":
    setup_logging()
    run()
