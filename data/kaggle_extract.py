"""
Approach B — Download and process real-world datasets for ALL roles.

Source 1: LeetCode company-wise problems from GitHub (no auth needed).
Source 2: Data Science/Analytics/Engineering job postings + skills from Kaggle.

Outputs role-prefixed JSON files to data/processed/ for load_kg.py.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests

from config import (
    ROLES, ROLE_SLUGS, COMPANIES, GITHUB_LEETCODE_BASE, LEETCODE_CSV_MAP,
    KAGGLE_DATASET, COMPANY_ALIASES, JOB_TITLE_KEYWORDS,
    LEETCODE_DIFFICULTY_FILTER, SQL_KEYWORDS, setup_logging,
)

logger = logging.getLogger(__name__)

TOP_N_PROBLEMS = 25
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "processed")

_CODING_ROUND: dict[str, dict[str, str]] = {
    "Data Scientist": {
        "Google": "Onsite: Coding", "Amazon": "Onsite: SQL Deep Dive",
        "Meta": "Onsite: Quantitative", "Apple": "Onsite: Coding",
        "Netflix": "Onsite: SQL & Analysis", "Microsoft": "Onsite: Coding",
        "Tesla": "Onsite: Coding", "TikTok": "Onsite: Coding", "Uber": "Onsite: Coding",
    },
    "Data Analyst": {
        "Google": "Onsite: SQL & Analysis", "Amazon": "Onsite: SQL & Case Study",
        "Meta": "Onsite: SQL & Metrics", "Apple": "Onsite: SQL & Business Analysis",
        "Netflix": "Onsite: SQL & Data Interpretation", "Microsoft": "Onsite: SQL & Analysis",
        "Tesla": "Onsite: SQL & Reporting", "TikTok": "Onsite: SQL & Metrics",
        "Uber": "Onsite: SQL & Analysis",
    },
    "Data Engineer": {
        "Google": "Onsite: Coding", "Amazon": "Onsite: Coding",
        "Meta": "Onsite: Coding 1", "Apple": "Onsite: Coding",
        "Netflix": "Onsite: Coding & Pipelines", "Microsoft": "Onsite: Coding",
        "Tesla": "Onsite: Coding", "TikTok": "Onsite: Coding 1", "Uber": "Onsite: Coding",
    },
}


def _skills_for_problem(title: str, role: str) -> list[str]:
    is_sql = any(kw in title.lower() for kw in SQL_KEYWORDS)
    if is_sql:
        return ["SQL", "Database Management"]
    if role == "Data Analyst":
        return ["Python", "Analytical Thinking"]
    return ["Python", "Data Structures & Algorithms"]


# ── Source 1: LeetCode ───────────────────────────────────────────────────────

def download_leetcode(role: str) -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = ROLE_SLUGS[role]
    allowed = set(LEETCODE_DIFFICULTY_FILTER.get(role, ["Easy", "Medium", "Hard"]))
    exp_levels = ["Entry", "Mid"] if role == "Data Analyst" else ["Entry", "Mid", "Senior"]
    total = 0

    for company in COMPANIES:
        csv_file = LEETCODE_CSV_MAP.get(company)
        if csv_file is None:
            continue

        url = f"{GITHUB_LEETCODE_BASE}/{csv_file}"
        logger.info("[%s] Downloading %s", company, csv_file)

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("[%s] Download failed: %s", company, exc)
            continue

        rows = [
            r for r in csv.DictReader(io.StringIO(resp.text))
            if r.get("Difficulty", "").strip() in allowed
        ]
        for row in rows:
            try:
                row["_freq"] = float(row.get("Frequency", 0))
            except (ValueError, TypeError):
                row["_freq"] = 0.0
        rows.sort(key=lambda r: r["_freq"], reverse=True)

        questions = []
        for i, row in enumerate(rows[:TOP_N_PROBLEMS]):
            title = row.get("Title", "").strip()
            questions.append({
                "id": f"{company}_{slug.upper()}_LC{i + 1}",
                "text": f"[LeetCode] {title}",
                "difficulty": row.get("Difficulty", "Medium").strip(),
                "source": "leetcode",
                "source_url": row.get("Leetcode Question Link", "").strip(),
                "acceptance": row.get("Acceptance", "").strip(),
                "round": _CODING_ROUND.get(role, {}).get(company, "Technical Screen"),
                "skills_tested": _skills_for_problem(title, role),
                "experience_levels": exp_levels,
            })

        outpath = os.path.join(OUTPUT_DIR, f"{slug}_leetcode_{company.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": company, "role": role, "questions": questions}, f, indent=2)

        logger.info("[%s] %d problems -> %s", company, len(questions), outpath)
        total += len(questions)

    logger.info("LeetCode total for %s: %d", role, total)
    return total


# ── Source 2: Kaggle ─────────────────────────────────────────────────────────

def _match_company(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    lower = name.lower().strip()
    for company, aliases in COMPANY_ALIASES.items():
        if any(a in lower for a in aliases):
            return company
    return None


def _is_role_title(title: str, role: str) -> bool:
    if not isinstance(title, str):
        return False
    lower = title.lower().strip()
    return any(kw in lower for kw in JOB_TITLE_KEYWORDS.get(role, []))


def download_job_skills(role: str) -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = ROLE_SLUGS[role]

    try:
        import kagglehub
    except ImportError:
        logger.warning("[Kaggle] kagglehub not installed — skipping")
        return 0

    logger.info("[Kaggle] Downloading dataset for %s...", role)
    try:
        path = kagglehub.dataset_download(KAGGLE_DATASET)
    except Exception as exc:
        logger.warning("[Kaggle] Download failed: %s", exc)
        return 0

    postings_path = os.path.join(path, "job_postings.csv")
    skills_path = os.path.join(path, "job_skills.csv")

    if not os.path.exists(postings_path) or not os.path.exists(skills_path):
        for root, _, files in os.walk(path):
            for fname in files:
                if fname == "job_postings.csv":
                    postings_path = os.path.join(root, fname)
                elif fname == "job_skills.csv":
                    skills_path = os.path.join(root, fname)

    if not os.path.exists(postings_path) or not os.path.exists(skills_path):
        logger.warning("[Kaggle] CSVs not found under %s", path)
        return 0

    postings_df = pd.read_csv(postings_path)
    skills_df = pd.read_csv(skills_path)
    logger.info("[Kaggle] %d postings, %d skill entries", len(postings_df), len(skills_df))

    company_col = next((c for c in ("company", "company_name") if c in postings_df.columns), None)
    title_col = next((c for c in ("title", "job_title", "job_name") if c in postings_df.columns), None)
    if not company_col or not title_col:
        logger.warning("[Kaggle] Missing columns. Have: %s", list(postings_df.columns))
        return 0

    postings_df["_co"] = postings_df[company_col].apply(_match_company)
    postings_df["_role"] = postings_df[title_col].apply(lambda t: _is_role_title(t, role))
    filtered = postings_df[(postings_df["_co"].notna()) & (postings_df["_role"])]
    logger.info("[Kaggle] %d matched postings", len(filtered))

    if filtered.empty:
        for co in COMPANIES:
            _write_empty_skills(slug, co, role)
        return 0

    join_col = next(
        (c for c in ("job_link", "job_id", "id") if c in postings_df.columns and c in skills_df.columns),
        None,
    )
    if not join_col:
        common = set(postings_df.columns) & set(skills_df.columns)
        join_col = next(iter(common), None)
    if not join_col:
        logger.warning("[Kaggle] No join column")
        return 0

    merged = filtered.merge(skills_df, on=join_col, how="inner")
    skill_col = next((c for c in ("skill", "skill_name", "skills") if c in merged.columns), None)
    if not skill_col:
        cands = [c for c in skills_df.columns if c != join_col]
        skill_col = cands[0] if cands else None
    if not skill_col:
        logger.warning("[Kaggle] No skill column")
        return 0

    total = 0
    for co in COMPANIES:
        sub = merged[merged["_co"] == co]
        if sub.empty:
            _write_empty_skills(slug, co, role)
            continue

        freq = sub[skill_col].value_counts()
        skills = []
        for rank, (name, count) in enumerate(freq.items()):
            if not isinstance(name, str) or not name.strip():
                continue
            if rank < len(freq) * 0.2:
                imp = "Critical"
            elif rank < len(freq) * 0.5:
                imp = "High"
            else:
                imp = "Medium"
            skills.append({"name": name.strip(), "importance": imp,
                           "category": "Technical", "source": "kaggle_job_postings",
                           "frequency": int(count)})

        outpath = os.path.join(OUTPUT_DIR, f"{slug}_job_skills_{co.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": co, "role": role, "skills": skills}, f, indent=2)
        logger.info("[%s] %d skills -> %s", co, len(skills), outpath)
        total += len(skills)

    logger.info("Kaggle total for %s: %d", role, total)
    return total


def _write_empty_skills(slug: str, company: str, role: str) -> None:
    outpath = os.path.join(OUTPUT_DIR, f"{slug}_job_skills_{company.lower()}.json")
    with open(outpath, "w") as f:
        json.dump({"company": company, "role": role, "skills": []}, f, indent=2)


# ── CLI ──────────────────────────────────────────────────────────────────────

def extract_role(role: str) -> None:
    logger.info("=" * 60)
    logger.info("Approach B: %s (%s)", role, ROLE_SLUGS[role])
    logger.info("=" * 60)
    download_leetcode(role)
    download_job_skills(role)


def extract_all() -> None:
    for role in ROLES:
        extract_role(role)


if __name__ == "__main__":
    import argparse

    setup_logging()
    parser = argparse.ArgumentParser(description="Approach B: real-world dataset extraction")
    parser.add_argument("--role", choices=ROLES, help="Single role")
    args = parser.parse_args()

    if args.role:
        extract_role(args.role)
    else:
        extract_all()
