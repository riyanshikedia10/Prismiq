"""
Data extraction pipeline: uses GPT-4o-mini to generate structured interview data
for all 5 FAANG companies for DATA ANALYST role, grounded by hard-coded seed
structures from verified sources.
Outputs JSON files to data/processed/{company}_da_data.json.
"""

import json
import os
import sys

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

COMPANIES = ["Google", "Amazon", "Meta", "Apple", "Netflix"]

# ---------------------------------------------------------------------------
# Hard-coded interview structures for Data Analyst roles
# DA interviews focus on SQL, Excel, business cases, metrics — not heavy ML/DSA
# ---------------------------------------------------------------------------

SEED_DATA = {
    "Google": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication"], "question_types": ["Resume walkthrough"]},
            {"name": "Technical Screen", "order": 2, "duration_min": 60,
             "skills_tested": ["SQL", "Spreadsheets"], "question_types": ["SQL query + data interpretation"]},
            {"name": "Onsite: SQL & Analysis", "order": 3, "duration_min": 45,
             "skills_tested": ["SQL", "Data Cleaning"], "question_types": ["Complex joins", "Aggregations"]},
            {"name": "Onsite: Quantitative", "order": 4, "duration_min": 45,
             "skills_tested": ["Statistics", "A/B Testing"],
             "question_types": ["Metric interpretation", "Hypothesis testing"]},
            {"name": "Onsite: Business Case", "order": 5, "duration_min": 45,
             "skills_tested": ["Product Metrics", "Business Sense"],
             "question_types": ["How would you measure success of X?", "Dashboard design"]},
            {"name": "Onsite: Googleyness", "order": 6, "duration_min": 45,
             "skills_tested": ["Culture Fit", "Leadership"],
             "question_types": ["Behavioral", "Teamwork"]},
        ],
    },
    "Amazon": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication", "Leadership Principles"],
             "question_types": ["Background + LP-based"]},
            {"name": "Technical Screen", "order": 2, "duration_min": 60,
             "skills_tested": ["SQL", "Excel"], "question_types": ["SQL on CollabEdit", "Data manipulation"]},
            {"name": "Onsite: SQL & Case Study", "order": 3, "duration_min": 45,
             "skills_tested": ["Advanced SQL", "Business Metrics"],
             "question_types": ["Multi-table joins", "Window functions", "KPI definition"]},
            {"name": "Onsite: Data Visualization", "order": 4, "duration_min": 45,
             "skills_tested": ["Tableau", "Excel", "Storytelling"],
             "question_types": ["Dashboard design", "Chart selection"]},
            {"name": "Onsite: Business Analysis", "order": 5, "duration_min": 45,
             "skills_tested": ["Business Metrics", "A/B Testing"],
             "question_types": ["Root cause analysis", "Product metrics cases"]},
            {"name": "Onsite: Bar Raiser", "order": 6, "duration_min": 45,
             "skills_tested": ["Leadership Principles"],
             "question_types": ["STAR behavioral questions"]},
        ],
    },
    "Meta": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication"], "question_types": ["Resume review"]},
            {"name": "Technical Screen", "order": 2, "duration_min": 45,
             "skills_tested": ["SQL", "Metrics"], "question_types": ["SQL + metric definition"]},
            {"name": "Onsite: SQL & Metrics", "order": 3, "duration_min": 45,
             "skills_tested": ["SQL", "Data Interpretation"],
             "question_types": ["Complex queries", "Metric debugging"]},
            {"name": "Onsite: Product Analytics", "order": 4, "duration_min": 45,
             "skills_tested": ["Product Analytics", "A/B Testing"],
             "question_types": ["Engagement dropped 5%, diagnose", "Feature launch analysis"]},
            {"name": "Onsite: Quantitative", "order": 5, "duration_min": 45,
             "skills_tested": ["Statistics", "Data Interpretation"],
             "question_types": ["Confidence intervals", "Sampling bias"]},
            {"name": "Onsite: Behavioral", "order": 6, "duration_min": 45,
             "skills_tested": ["Impact", "Collaboration"],
             "question_types": ["Data-driven decision stories"]},
        ],
    },
    "Apple": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication"], "question_types": ["Resume + motivation"]},
            {"name": "Phone Screen", "order": 2, "duration_min": 60,
             "skills_tested": ["SQL", "Excel", "Statistics"], "question_types": ["SQL + spreadsheet basics"]},
            {"name": "Onsite: SQL & Business Analysis", "order": 3, "duration_min": 45,
             "skills_tested": ["SQL", "Business Analysis"],
             "question_types": ["Data extraction", "Report generation"]},
            {"name": "Onsite: Data Visualization", "order": 4, "duration_min": 45,
             "skills_tested": ["Tableau", "Data Storytelling"],
             "question_types": ["Dashboard design", "Insight presentation"]},
            {"name": "Onsite: Domain", "order": 5, "duration_min": 45,
             "skills_tested": ["Domain Expertise", "Product"],
             "question_types": ["Team-specific questions"]},
            {"name": "Onsite: Behavioral", "order": 6, "duration_min": 45,
             "skills_tested": ["Collaboration", "Innovation"],
             "question_types": ["Handling ambiguity"]},
        ],
    },
    "Netflix": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication", "Impact"],
             "question_types": ["Background", "Data-driven decisions"]},
            {"name": "Technical Screen", "order": 2, "duration_min": 60,
             "skills_tested": ["SQL", "Excel"], "question_types": ["SQL + data interpretation"]},
            {"name": "Onsite: SQL & Data Interpretation", "order": 3, "duration_min": 60,
             "skills_tested": ["SQL", "Behavioral Data"],
             "question_types": ["Engagement metrics", "Cohort analysis"]},
            {"name": "Onsite: Business Case", "order": 4, "duration_min": 60,
             "skills_tested": ["A/B Testing", "Metrics"],
             "question_types": ["Experiment design", "KPI selection"]},
            {"name": "Onsite: Data Storytelling", "order": 5, "duration_min": 60,
             "skills_tested": ["Visualization", "Communication"],
             "question_types": ["Present findings to stakeholders", "Chart selection"]},
            {"name": "Onsite: Culture", "order": 6, "duration_min": 45,
             "skills_tested": ["Autonomy", "Ownership"],
             "question_types": ["Freedom & responsibility"]},
        ],
    },
}


GPT_EXTRACTION_PROMPT = """You are an expert on FAANG Data Analyst interviews.

I'm building a Knowledge Graph for interview preparation. For {company}, I need you to generate
structured interview data in JSON format.

EXISTING ROUND STRUCTURE (verified — do NOT change these):
{seed_rounds}

Generate the following additional data:

1. "skills" — A list of 10-15 skills tested at {company} for Data Analyst roles.
   Each skill: {{"name": "...", "importance": "Critical|High|Medium", "category": "Technical|Behavioral"}}
   Focus on: SQL, Excel/Sheets, Tableau/Looker, Python (pandas), Statistics, Business Metrics,
   A/B Testing, Data Cleaning, Data Storytelling, Communication.

2. "sample_questions" — 15-20 realistic interview questions across all rounds.
   Each question: {{
     "text": "...",
     "round": "<must match a round name from above>",
     "difficulty": "Easy|Medium|Hard",
     "skills_tested": ["..."],
     "experience_levels": ["Entry|Mid|Senior"]
   }}
   Include questions for ALL experience levels and ALL rounds.
   Make questions specific to {company}'s culture and interview style.
   Focus on SQL queries, metric definition, dashboard design, business cases — NOT ML/coding.

3. "learning_resources" — 8-12 learning resources for the key skills.
   Each resource: {{"name": "...", "url": "...", "skill": "...", "type": "Course|Book|Tool|Article"}}
   Use real, well-known resources (DataLemur, Mode SQL Tutorial, Coursera, W3Schools, etc.)

Return ONLY valid JSON with keys: "skills", "sample_questions", "learning_resources".
"""


def extract_company_data(company: str) -> dict:
    """Use GPT-4o-mini to extract structured DA interview data for a company."""
    seed_rounds = json.dumps(SEED_DATA[company]["rounds"], indent=2)

    prompt = GPT_EXTRACTION_PROMPT.format(company=company, seed_rounds=seed_rounds)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    extracted = json.loads(response.choices[0].message.content)
    extracted["rounds"] = SEED_DATA[company]["rounds"]

    return extracted


def save_company_data(company: str, data: dict):
    """Save extracted data to data/processed/{company}_da_data.json."""
    os.makedirs("data/processed", exist_ok=True)
    filepath = f"data/processed/{company.lower()}_da_data.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {filepath}")


def extract_all():
    """Run extraction for all 5 companies."""
    print("Starting GPT-4o-mini Data Analyst extraction...\n")

    for company in COMPANIES:
        print(f"[{company}] Extracting DA interview data...")
        try:
            data = extract_company_data(company)
            save_company_data(company, data)

            n_skills = len(data.get("skills", []))
            n_questions = len(data.get("sample_questions", []))
            n_resources = len(data.get("learning_resources", []))
            print(f"  → {n_skills} skills, {n_questions} questions, {n_resources} resources\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")
            sys.exit(1)

    print("DA extraction complete. Files in data/processed/")


if __name__ == "__main__":
    extract_all()
