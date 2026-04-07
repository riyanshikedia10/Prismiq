"""
Question generation using GPT-4o-mini, grounded by Knowledge Graph context.
Tailored for Data Analyst interview preparation.
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are an expert interview coach specializing in Data Analyst interviews \
at top tech companies. You generate realistic, targeted interview questions that match each \
company's specific interview style, difficulty level, and round format. \
Focus on SQL, business metrics, data visualization, Excel, and analytical reasoning — \
NOT machine learning or advanced coding."""

GENERATION_PROMPT = """Generate ONE new interview question for the following context.

COMPANY: {company}
ROLE: {role}
EXPERIENCE LEVEL: {experience_level}
INTERVIEW ROUND: {round_name}
SKILLS TESTED IN THIS ROUND: {skills_list}
COMPANY'S CRITICAL SKILLS: {critical_skills}

SAMPLE QUESTIONS FROM THIS COMPANY (for style reference — generate something DIFFERENT):
{sample_questions}

Requirements:
1. The question must test the skills listed above
2. Difficulty must be appropriate for {experience_level} level
3. Match {company}'s known interview style and culture
4. Be specific and realistic — include a concrete scenario when possible
5. Be different from the sample questions provided
6. For SQL rounds: include table schemas and expected output format
7. For business case rounds: include specific metrics and context
8. For visualization rounds: specify the data and audience

Return your response as JSON with these keys:
- "question": the full question text
- "skills_tested": list of skills this question tests
- "difficulty": "Easy", "Medium", or "Hard"
- "round": the interview round name
- "hints": list of 2-3 hints the candidate could use if stuck
"""


def generate_question(
    company: str,
    role: str = "Data Analyst",
    experience_level: str = "Entry",
    round_name: str = "Technical Screen",
    kg_context: dict = None,
) -> dict:
    """
    Generate a targeted DA interview question using KG context.

    Args:
        company: Company name (e.g. "Google")
        role: Role name (default "Data Analyst")
        experience_level: "Entry", "Mid", or "Senior"
        round_name: Interview round name (e.g. "Onsite: SQL & Analysis")
        kg_context: Full context dict from kg_retrieval.get_context_for_generation()

    Returns:
        dict with question, skills_tested, difficulty, round, hints
    """
    if kg_context is None:
        kg_context = {}

    # Extract skills for the specific round
    round_skills = []
    if kg_context.get("round_details") and kg_context["round_details"].get("skills"):
        round_skills = [s["skill"] for s in kg_context["round_details"]["skills"]]

    if not round_skills:
        # Fall back to company-wide skills
        round_skills = [s["name"] for s in kg_context.get("skills", [])]

    # Critical skills
    critical = [
        s["name"] for s in kg_context.get("skills", [])
        if s.get("importance") == "Critical"
    ]

    # Sample questions for style reference (limit to 5)
    samples = kg_context.get("sample_questions", [])
    if kg_context.get("round_details") and kg_context["round_details"].get("questions"):
        samples = kg_context["round_details"]["questions"]
    sample_texts = [q.get("question", q.get("text", "")) for q in samples[:5]]

    prompt = GENERATION_PROMPT.format(
        company=company,
        role=role,
        experience_level=experience_level,
        round_name=round_name,
        skills_list=", ".join(round_skills),
        critical_skills=", ".join(critical),
        sample_questions="\n".join(f"- {q}" for q in sample_texts) if sample_texts else "None available",
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    result = json.loads(response.choices[0].message.content)

    result.setdefault("skills_tested", round_skills[:3])
    result.setdefault("difficulty", "Medium")
    result.setdefault("round", round_name)
    result.setdefault("hints", [])

    return result
