"""
Approach B: Download and process real-world datasets.

Source 1 — LeetCode company-wise problems from GitHub (no auth needed).
Source 2 — Data Science job postings + skills from Kaggle (needs kagglehub auth).

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

TOP_N_PROBLEMS = 25

CODING_ROUND_MAP = {
    "Google": "Onsite: Coding",
    "Amazon": "Onsite: SQL Deep Dive",
    "Meta": "Onsite: Quantitative",
    "Apple": "Onsite: Coding",
    "Netflix": "Onsite: SQL & Analysis",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "processed")


# ── Source 1: LeetCode from GitHub ───────────────────────────────────────────

def download_leetcode_data():
    """Download LeetCode CSVs from GitHub, process top problems per company."""
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

        # Sort by frequency (descending) and take top N
        for row in rows:
            try:
                row["_freq"] = float(row.get("Frequency", 0))
            except (ValueError, TypeError):
                row["_freq"] = 0.0

        rows.sort(key=lambda r: r["_freq"], reverse=True)
        top = rows[:TOP_N_PROBLEMS]

        questions = []
        for i, row in enumerate(top):
            title = row.get("Title", "").strip()
            difficulty = row.get("Difficulty", "Medium").strip()
            link = row.get("Leetcode Question Link", "").strip()
            acceptance = row.get("Acceptance", "").strip()

            questions.append({
                "id": f"{company}_LC{i+1}",
                "text": f"[LeetCode] {title}",
                "difficulty": difficulty,
                "source": "leetcode",
                "source_url": link,
                "acceptance": acceptance,
                "round": CODING_ROUND_MAP.get(company, "Technical Screen"),
                "skills_tested": ["Python", "Data Structures & Algorithms"],
                "experience_levels": ["Entry", "Mid", "Senior"],
            })

        outpath = os.path.join(OUTPUT_DIR, f"leetcode_{company.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": company, "questions": questions}, f, indent=2)

        print(f"  [{company}] Saved {len(questions)} problems → {outpath}")
        total += len(questions)

    print(f"\n  LeetCode total: {total} problems across all companies")
    return total


# ── Source 2: Kaggle Job Postings ────────────────────────────────────────────

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


def download_job_skills_data():
    """Download DS job postings from Kaggle and extract skill frequencies."""
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
        # Try to locate the files anywhere under the download path
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

    # Identify the company column (could be 'company' or 'company_name')
    company_col = None
    for col in ["company", "company_name"]:
        if col in postings_df.columns:
            company_col = col
            break

    if company_col is None:
        print(f"  [Kaggle] No company column found. Columns: {list(postings_df.columns)}")
        return 0

    # Map companies to FAANG
    postings_df["faang"] = postings_df[company_col].apply(_match_company)
    faang_postings = postings_df[postings_df["faang"].notna()]
    print(f"  [Kaggle] {len(faang_postings)} FAANG postings found")

    if faang_postings.empty:
        print("  [Kaggle] No FAANG postings matched — saving empty files")
        for company in FAANG_ALIASES:
            outpath = os.path.join(OUTPUT_DIR, f"job_skills_{company.lower()}.json")
            with open(outpath, "w") as f:
                json.dump({"company": company, "skills": []}, f, indent=2)
        return 0

    # Join skills with FAANG postings
    join_col = None
    for col in ["job_link", "job_id", "id"]:
        if col in postings_df.columns and col in skills_df.columns:
            join_col = col
            break

    if join_col is None:
        # Try matching on index or first common column
        common = set(postings_df.columns) & set(skills_df.columns)
        if common:
            join_col = list(common)[0]
        else:
            print(f"  [Kaggle] No common join column between postings and skills")
            return 0

    merged = faang_postings.merge(skills_df, on=join_col, how="inner")

    # Identify skill column
    skill_col = None
    for col in ["skill", "skill_name", "skills"]:
        if col in merged.columns:
            skill_col = col
            break

    if skill_col is None:
        # Use any column from skills_df that isn't the join column
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
            outpath = os.path.join(OUTPUT_DIR, f"job_skills_{company.lower()}.json")
            with open(outpath, "w") as f:
                json.dump({"company": company, "skills": []}, f, indent=2)
            continue

        # Count skill frequencies
        freq = company_skills[skill_col].value_counts()

        skills = []
        for rank, (skill_name, count) in enumerate(freq.items()):
            if not isinstance(skill_name, str) or not skill_name.strip():
                continue

            # Assign importance by rank
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

        outpath = os.path.join(OUTPUT_DIR, f"job_skills_{company.lower()}.json")
        with open(outpath, "w") as f:
            json.dump({"company": company, "skills": skills}, f, indent=2)

        print(f"  [{company}] {len(skills)} verified skills → {outpath}")
        total += len(skills)

    print(f"\n  Kaggle total: {total} verified skills across all companies")
    return total


# ── Main ─────────────────────────────────────────────────────────────────────

def extract_all():
    """Run both data sources. LeetCode always runs; Kaggle gracefully degrades."""
    print("=" * 50)
    print("Approach B: Real-World Dataset Extraction")
    print("=" * 50)

    print("\n--- Source 1: LeetCode (GitHub) ---")
    lc_count = download_leetcode_data()

    print("\n--- Source 2: Job Postings (Kaggle) ---")
    jk_count = download_job_skills_data()

    print(f"\n{'=' * 50}")
    print(f"Done. LeetCode: {lc_count} problems, Kaggle: {jk_count} skills")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    extract_all()
