"""
Approach B: Download and process real-world datasets for Data Analyst role.

Source 1 — LeetCode company-wise SQL/Easy-Medium problems from GitHub.
Source 2 — Data Analyst job postings + skills from Kaggle (needs kagglehub auth).

Outputs JSON files to data/processed/ for load_kg.py to consume.
"""

import csv
import io
import json
import os
import sys

import pandas as pd
import requests

# ── Config ───────────────────────────────────────────────────────────────────

GITHUB_BASE = (
    "https://raw.githubusercontent.com/krishnadey30/"
    "LeetCode-Questions-CompanyWise/master"
)

COMPANY_CSV_MAP = {
    "Google": "google_alltime.csv",
    "Amazon": "amazon_alltime.csv",
    "Meta": "facebook_alltime.csv",
    "Apple": "apple_alltime.csv",
    "Netflix": None,  # Netflix rarely appears in LeetCode datasets
}

KAGGLE_DATASET = "asaniczka/data-science-job-postings-and-skills"

FAANG_ALIASES = {
    "Google": ["google", "alphabet"],
    "Amazon": ["amazon", "aws"],
    "Meta": ["meta", "facebook"],
    "Apple": ["apple"],
    "Netflix": ["netflix"],
}

# Data Analyst interviews focus on SQL, Excel, case studies — not heavy DSA
TOP_N_PROBLEMS = 50

# DA-specific interview round mapping
INTERVIEW_ROUND_MAP = {
    "Google": "Onsite: SQL & Analysis",
    "Amazon": "Onsite: SQL & Case Study",
    "Meta": "Onsite: SQL & Metrics",
    "Apple": "Onsite: SQL & Business Analysis",
    "Netflix": "Onsite: SQL & Data Interpretation",
}

# Filter LeetCode for these difficulties (DA roles = Easy/Medium, not Hard)
DA_DIFFICULTY_FILTER = ["Easy", "Medium"]

# Keywords to identify SQL/DA-relevant LeetCode problems
SQL_KEYWORDS = [
    "sql", "database", "table", "query", "select", "join",
    "department", "employee", "salary", "manager", "customer",
    "duplicate", "consecutive", "rank", "nth", "second highest",
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "processed")


# ── Source 1: LeetCode from GitHub ───────────────────────────────────────────

def _is_da_relevant(row: dict) -> bool:
    """Check if a LeetCode problem is relevant to Data Analyst interviews."""
    title = row.get("Title", "").lower()
    difficulty = row.get("Difficulty", "").strip()

    # Filter by difficulty — DA roles rarely ask Hard problems
    if difficulty not in DA_DIFFICULTY_FILTER:
        return False

    # Boost SQL/database-related problems
    for keyword in SQL_KEYWORDS:
        if keyword in title:
            return True

    # Still include Easy/Medium problems (general analytical thinking)
    return True


def download_leetcode_data():
    """Download LeetCode CSVs from GitHub, filter for DA-relevant problems."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = 0

    for company, csv_file in COMPANY_CSV_MAP.items():
        if csv_file is None:
            print(f"  [{company}] No LeetCode CSV available, skipping")
            continue

        url = f"{GITHUB_BASE}/{csv_file}"
        print(f"  [{company}] Downloading {csv_file}...")

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [{company}] Download failed: {e}")
            continue

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)

        # Filter for DA-relevant problems first
        da_rows = [r for r in rows if _is_da_relevant(r)]

        # Sort by frequency (descending) and take top N
        for row in da_rows:
            try:
                row["_freq"] = float(row.get("Frequency", 0))
            except (ValueError, TypeError):
                row["_freq"] = 0.0

        da_rows.sort(key=lambda r: r["_freq"], reverse=True)
        top = da_rows[:TOP_N_PROBLEMS]

        questions = []
        for i, row in enumerate(top):
            title = row.get("Title", "").strip()
            difficulty = row.get("Difficulty", "Medium").strip()
            link = row.get("Leetcode Question Link", "").strip()
            acceptance = row.get("Acceptance", "").strip()

            # Determine skills tested based on problem type
            title_lower = title.lower()
            if any(kw in title_lower for kw in SQL_KEYWORDS):
                skills = ["SQL", "Database Management"]
            else:
                skills = ["Python", "Analytical Thinking"]

            questions.append({
                "id": f"{company}_DA_LC{i+1}",
                "text": f"[LeetCode] {title}",
                "difficulty": difficulty,
                "source": "leetcode",
                "source_url": link,
                "acceptance": acceptance,
                "round": INTERVIEW_ROUND_MAP.get(company, "Technical Screen"),
                "skills_tested": skills,
                "experience_levels": ["Entry", "Mid"],
            })

        outpath = os.path.join(OUTPUT_DIR, f"da_leetcode_{company.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": company, "questions": questions}, f, indent=2)

        print(f"  [{company}] Saved {len(questions)} DA problems → {outpath}")
        total += len(questions)

    print(f"\n  LeetCode total: {total} DA-relevant problems across all companies")
    return total


# ── Source 2: Kaggle Job Postings ────────────────────────────────────────────

# Job title keywords to filter for Data Analyst roles
DA_TITLE_KEYWORDS = [
    "data analyst", "business analyst", "analytics analyst",
    "reporting analyst", "bi analyst", "business intelligence analyst",
    "junior data analyst", "senior data analyst",
]


def _match_company(name: str) -> str | None:
    """Check if a company name matches any FAANG alias."""
    if not isinstance(name, str):
        return None
    lower = name.lower().strip()
    for company, aliases in FAANG_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                return company
    return None


def _is_da_title(title: str) -> bool:
    """Check if a job title is a Data Analyst role."""
    if not isinstance(title, str):
        return False
    lower = title.lower().strip()
    return any(kw in lower for kw in DA_TITLE_KEYWORDS)


def download_job_skills_data():
    """Download job postings from Kaggle and extract DA-specific skill frequencies."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        import kagglehub
    except ImportError:
        print("  [Kaggle] kagglehub not installed — skipping job skills download")
        print("  [Kaggle] Run: pip install kagglehub")
        return 0

    print("  [Kaggle] Downloading job postings dataset...")
    try:
        path = kagglehub.dataset_download(KAGGLE_DATASET)
    except Exception as e:
        print(f"  [Kaggle] Download failed: {e}")
        print("  [Kaggle] Make sure ~/.kaggle/kaggle.json exists or set")
        print("           KAGGLE_USERNAME and KAGGLE_KEY in your .env")
        return 0

    print(f"  [Kaggle] Dataset at: {path}")

    # Find CSV files
    postings_path = os.path.join(path, "job_postings.csv")
    skills_path = os.path.join(path, "job_skills.csv")

    if not os.path.exists(postings_path) or not os.path.exists(skills_path):
        for root, _dirs, files in os.walk(path):
            for fname in files:
                if fname == "job_postings.csv":
                    postings_path = os.path.join(root, fname)
                elif fname == "job_skills.csv":
                    skills_path = os.path.join(root, fname)

    if not os.path.exists(postings_path):
        print(f"  [Kaggle] job_postings.csv not found under {path}")
        return 0
    if not os.path.exists(skills_path):
        print(f"  [Kaggle] job_skills.csv not found under {path}")
        return 0

    postings_df = pd.read_csv(postings_path)
    skills_df = pd.read_csv(skills_path)

    print(f"  [Kaggle] Loaded {len(postings_df)} postings, {len(skills_df)} skill entries")

    # Identify the company column
    company_col = None
    for col in ["company", "company_name"]:
        if col in postings_df.columns:
            company_col = col
            break

    if company_col is None:
        print(f"  [Kaggle] No company column found. Columns: {list(postings_df.columns)}")
        return 0

    # Identify the title column
    title_col = None
    for col in ["title", "job_title", "job_name"]:
        if col in postings_df.columns:
            title_col = col
            break

    if title_col is None:
        print(f"  [Kaggle] No title column found. Columns: {list(postings_df.columns)}")
        return 0

    # Filter for Data Analyst titles AND FAANG companies
    postings_df["faang"] = postings_df[company_col].apply(_match_company)
    postings_df["is_da"] = postings_df[title_col].apply(_is_da_title)

    faang_da_postings = postings_df[
        (postings_df["faang"].notna()) & (postings_df["is_da"])
    ]
    print(f"  [Kaggle] {len(faang_da_postings)} FAANG Data Analyst postings found")

    if faang_da_postings.empty:
        print("  [Kaggle] No FAANG DA postings matched — saving empty files")
        for company in FAANG_ALIASES:
            outpath = os.path.join(OUTPUT_DIR, f"da_job_skills_{company.lower()}.json")
            with open(outpath, "w") as f:
                json.dump({"company": company, "skills": []}, f, indent=2)
        return 0

    # Join skills with FAANG DA postings
    join_col = None
    for col in ["job_link", "job_id", "id"]:
        if col in postings_df.columns and col in skills_df.columns:
            join_col = col
            break

    if join_col is None:
        common = set(postings_df.columns) & set(skills_df.columns)
        if common:
            join_col = list(common)[0]
        else:
            print(f"  [Kaggle] No common join column between postings and skills")
            return 0

    merged = faang_da_postings.merge(skills_df, on=join_col, how="inner")

    # Identify skill column
    skill_col = None
    for col in ["skill", "skill_name", "skills"]:
        if col in merged.columns:
            skill_col = col
            break

    if skill_col is None:
        skill_candidates = [c for c in skills_df.columns if c != join_col]
        if skill_candidates:
            skill_col = skill_candidates[0]
        else:
            print(f"  [Kaggle] No skill column identified")
            return 0

    total = 0
    for company in FAANG_ALIASES:
        company_skills = merged[merged["faang"] == company]
        if company_skills.empty:
            outpath = os.path.join(OUTPUT_DIR, f"da_job_skills_{company.lower()}.json")
            with open(outpath, "w") as f:
                json.dump({"company": company, "skills": []}, f, indent=2)
            continue

        # Count skill frequencies
        freq = company_skills[skill_col].value_counts()

        skills = []
        for rank, (skill_name, count) in enumerate(freq.items()):
            if not isinstance(skill_name, str) or not skill_name.strip():
                continue

            if rank < len(freq) * 0.2:
                importance = "Critical"
            elif rank < len(freq) * 0.5:
                importance = "High"
            else:
                importance = "Medium"

            skills.append({
                "name": skill_name.strip(),
                "importance": importance,
                "category": "Technical",
                "source": "kaggle_job_postings",
                "frequency": int(count),
            })

        outpath = os.path.join(OUTPUT_DIR, f"da_job_skills_{company.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": company, "skills": skills}, f, indent=2)

        print(f"  [{company}] {len(skills)} DA-verified skills → {outpath}")
        total += len(skills)

    print(f"\n  Kaggle total: {total} DA-verified skills across all companies")
    return total


# ── Main ─────────────────────────────────────────────────────────────────────

def extract_all():
    """Run both data sources for Data Analyst role."""
    print("=" * 50)
    print("Approach B: Real-World Dataset Extraction (Data Analyst)")
    print("=" * 50)

    print("\n--- Source 1: LeetCode (GitHub) — DA Filtered ---")
    lc_count = download_leetcode_data()

    print("\n--- Source 2: Job Postings (Kaggle) — DA Filtered ---")
    jk_count = download_job_skills_data()

    print(f"\n{'=' * 50}")
    print(f"Done. LeetCode: {lc_count} DA problems, Kaggle: {jk_count} DA skills")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    extract_all()
