"""
Data extraction pipeline: uses GPT-4o-mini to generate structured interview data
for all 5 FAANG companies, grounded by hard-coded seed structures from verified sources.
Outputs JSON files to data/processed/{company}_data.json.
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
# Hard-coded interview structures from architecture spec (Section 4d)
# These ground the GPT extraction and ensure accuracy.
# ---------------------------------------------------------------------------

SEED_DATA = {
    "Google": {
        "rounds": [
            {"name": "Recruiter Screen", "order": 1, "duration_min": 30,
             "skills_tested": ["Communication"], "question_types": ["Resume walkthrough"]},
            {"name": "Technical Screen", "order": 2, "duration_min": 60,
             "skills_tested": ["SQL", "Python", "Statistics"], "question_types": ["1 SQL + 1 Python problem"]},
            {"name": "Onsite: Coding", "order": 3, "duration_min": 45,
             "skills_tested": ["SQL", "Python"], "question_types": ["Live coding on shared doc"]},
            {"name": "Onsite: Stats & ML", "order": 4, "duration_min": 45,
             "skills_tested": ["Probability", "A/B Testing", "Machine Learning"],
             "question_types": ["Statistical inference", "Model evaluation"]},
            {"name": "Onsite: Product Case", "order": 5, "duration_min": 45,
             "skills_tested": ["Product Metrics", "Business Sense"],
             "question_types": ["How would you measure success of X?"]},
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
             "skills_tested": ["SQL"], "question_types": ["Complex SQL on CollabEdit"]},
            {"name": "Onsite: SQL Deep Dive", "order": 3, "duration_min": 45,
             "skills_tested": ["Advanced SQL"], "question_types": ["Multi-table", "Window functions"]},
            {"name": "Onsite: Coding & ML", "order": 4, "duration_min": 45,
             "skills_tested": ["Python", "Machine Learning"], "question_types": ["Pandas", "Model building"]},
            {"name": "Onsite: Case Study", "order": 5, "duration_min": 45,
             "skills_tested": ["Business Metrics", "A/B Testing"],
             "question_types": ["Product metrics cases"]},
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
             "skills_tested": ["SQL", "Probability"], "question_types": ["SQL + probability puzzles"]},
            {"name": "Onsite: Quantitative", "order": 3, "duration_min": 45,
             "skills_tested": ["SQL", "Metrics"], "question_types": ["Complex queries", "Metric definition"]},
            {"name": "Onsite: Product Sense", "order": 4, "duration_min": 45,
             "skills_tested": ["Product Analytics", "A/B Testing"],
             "question_types": ["Engagement dropped 5%, diagnose"]},
            {"name": "Onsite: Stats", "order": 5, "duration_min": 45,
             "skills_tested": ["Statistics", "Causal Inference"],
             "question_types": ["Power analysis", "Confidence intervals"]},
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
             "skills_tested": ["SQL", "Python", "Statistics"], "question_types": ["Coding + stats basics"]},
            {"name": "Onsite: Technical", "order": 3, "duration_min": 45,
             "skills_tested": ["Machine Learning", "Statistical Modeling"],
             "question_types": ["Algorithm selection", "Model evaluation"]},
            {"name": "Onsite: Coding", "order": 4, "duration_min": 45,
             "skills_tested": ["Python", "Data Manipulation"],
             "question_types": ["End-to-end data pipeline"]},
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
             "skills_tested": ["SQL", "Statistics"], "question_types": ["SQL + statistical reasoning"]},
            {"name": "Onsite: SQL & Analysis", "order": 3, "duration_min": 60,
             "skills_tested": ["SQL", "Behavioral Data"],
             "question_types": ["Engagement metrics", "Cohort analysis"]},
            {"name": "Onsite: Experimentation", "order": 4, "duration_min": 60,
             "skills_tested": ["A/B Testing", "Causal Inference"],
             "question_types": ["Design experiments", "Diagnose bias"]},
            {"name": "Onsite: Product", "order": 5, "duration_min": 60,
             "skills_tested": ["Product Metrics", "Business"],
             "question_types": ["Feature evaluation", "Growth metrics"]},
            {"name": "Onsite: Culture", "order": 6, "duration_min": 45,
             "skills_tested": ["Autonomy", "Ownership"],
             "question_types": ["Freedom & responsibility"]},
        ],
    },
}


GPT_EXTRACTION_PROMPT = """You are an expert on FAANG Data Scientist interviews.

I'm building a Knowledge Graph for interview preparation. For {company}, I need you to generate
structured interview data in JSON format.

EXISTING ROUND STRUCTURE (verified — do NOT change these):
{seed_rounds}

Generate the following additional data:

1. "skills" — A list of 10-15 skills tested at {company} for Data Scientist roles.
   Each skill: {{"name": "...", "importance": "Critical|High|Medium", "category": "Technical|Behavioral"}}

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

3. "learning_resources" — 8-12 learning resources for the key skills.
   Each resource: {{"name": "...", "url": "...", "skill": "...", "type": "Course|Book|Tool|Article"}}
   Use real, well-known resources (DataLemur, LeetCode, StatQuest, Coursera, etc.)

Return ONLY valid JSON with keys: "skills", "sample_questions", "learning_resources".
"""


def extract_company_data(company: str) -> dict:
    """Use GPT-4o-mini to extract structured interview data for a company."""
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
    """Save extracted data to data/processed/{company}_data.json."""
    os.makedirs("data/processed", exist_ok=True)
    filepath = f"data/processed/{company.lower()}_data.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {filepath}")


def extract_all():
    """Run extraction for all 5 companies."""
    print("Starting GPT-4o-mini data extraction...\n")

    for company in COMPANIES:
        print(f"[{company}] Extracting...")
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

    print("Extraction complete. Files in data/processed/")


if __name__ == "__main__":
    extract_all()
