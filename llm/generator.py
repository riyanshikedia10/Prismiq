"""
Question generation using GPT-4o-mini, grounded by Knowledge Graph context.
Role-aware with retry logic and structured output validation.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import GeneratedQuestion, LLMError

logger = logging.getLogger(__name__)

# ── Role-specific system prompts ─────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "Data Scientist": (
        "You are an expert interview coach specializing in Data Scientist interviews "
        "at top tech companies. Focus on ML, statistics, coding, A/B testing, and product metrics."
    ),
    "Data Analyst": (
        "You are an expert interview coach specializing in Data Analyst interviews "
        "at top tech companies. Focus on SQL, business metrics, data visualization, "
        "Excel, and analytical reasoning — NOT ML or advanced coding."
    ),
    "Data Engineer": (
        "You are an expert interview coach specializing in Data Engineer interviews "
        "at top tech companies. Focus on system design, data pipelines, SQL, Python, "
        "Spark, Kafka, Airflow, data modeling, and cloud infrastructure."
    ),
}

_GENERATION_PROMPT = """Generate ONE new interview question for the following context.

COMPANY: {company}
ROLE: {role}
EXPERIENCE LEVEL: {experience_level}
INTERVIEW ROUND: {round_name}
SKILLS TESTED IN THIS ROUND: {skills_list}
COMPANY'S CRITICAL SKILLS: {critical_skills}

SAMPLE QUESTIONS (for style reference — generate something DIFFERENT):
{sample_questions}

Requirements:
1. Test the skills listed above
2. Difficulty appropriate for {experience_level} level
3. Match {company}'s known interview style
4. Be specific and realistic with a concrete scenario
5. For Recruiter Screen: Ask screening questions ONLY — "Walk me through your resume",
   "Why {company}?", "What interests you about this role?", "Tell me about your background".
   NO STAR behavioral, NO technical deep-dives. Keep it conversational and short.
6. For SQL rounds: include table schemas
7. For system design rounds: include scale constraints
8. For business case rounds: include specific metrics
9. For behavioral rounds: use STAR format about past experiences

Return JSON: {{"question":"…","skills_tested":[…],"difficulty":"Easy|Medium|Hard","round":"…","hints":[…]}}
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def _call_openai(client: OpenAI, system: str, user: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise LLMError("Empty response from GPT")
    return json.loads(raw)


def generate_question(
    company: str,
    role: str = "Data Scientist",
    experience_level: str = "Mid",
    round_name: str = "Technical Screen",
    kg_context: dict | None = None,
) -> dict:
    """
    Generate a targeted interview question using KG context.

    Returns a dict matching GeneratedQuestion schema.
    """
    from config import get_settings

    if kg_context is None:
        kg_context = {}

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # Classify the round type
    rn_lower = round_name.lower()
    _RECRUITER_KEYWORDS = {"recruiter", "phone screen"}
    _BEHAVIORAL_KEYWORDS = {"behavioral", "culture", "bar raiser", "googleyness", "as appropriate"}
    is_recruiter = any(kw in rn_lower for kw in _RECRUITER_KEYWORDS)
    is_behavioral = any(kw in rn_lower for kw in _BEHAVIORAL_KEYWORDS)

    # For recruiter/behavioral rounds, hard-code appropriate skills regardless of KG.
    # This prevents technical skills from leaking in via question linkages.
    if is_recruiter:
        round_skills = ["Communication", "Background", "Motivation"]
    elif is_behavioral:
        round_skills = ["Communication", "Leadership", "Teamwork", "Problem Solving"]
    else:
        round_skills = []
        if kg_context.get("round_details") and kg_context["round_details"].get("skills"):
            round_skills = [s["skill"] for s in kg_context["round_details"]["skills"]]
        if not round_skills:
            round_skills = [s["name"] for s in kg_context.get("skills", [])]

    critical = [
        s["name"] for s in kg_context.get("skills", [])
        if s.get("importance") == "Critical"
    ]

    samples = kg_context.get("sample_questions", [])
    if kg_context.get("round_details") and kg_context["round_details"].get("questions"):
        samples = kg_context["round_details"]["questions"]
    sample_texts = [q.get("question", q.get("text", "")) for q in samples[:5]]

    prompt = _GENERATION_PROMPT.format(
        company=company,
        role=role,
        experience_level=experience_level,
        round_name=round_name,
        skills_list=", ".join(round_skills) or "General",
        critical_skills=", ".join(critical) or "N/A",
        sample_questions="\n".join(f"- {q}" for q in sample_texts) if sample_texts else "None available",
    )

    system_prompt = _SYSTEM_PROMPTS.get(role, _SYSTEM_PROMPTS["Data Scientist"])

    logger.debug("Generating question for %s / %s / %s / %s", company, role, experience_level, round_name)
    raw = _call_openai(client, system_prompt, prompt)

    result = GeneratedQuestion.model_validate(raw)
    out = result.model_dump()

    if not out["skills_tested"]:
        out["skills_tested"] = round_skills[:3]
    if not out["round"]:
        out["round"] = round_name

    return out
