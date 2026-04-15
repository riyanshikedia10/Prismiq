"""
Answer evaluation and reasoning path explanation using GPT-4o-mini.
Role-aware scoring guides with retry logic and validated output.
"""

from __future__ import annotations

import json
import logging
import os

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import EvaluationResult, LLMError

logger = logging.getLogger(__name__)

# ── Scoring guides per role ──────────────────────────────────────────────────

_SCORING_GUIDES: dict[str, str] = {
    "Data Scientist": (
        "1-3: Major gaps, missing core concepts\n"
        "4-5: Partial understanding, significant gaps\n"
        "6-7: Good grasp, some areas to strengthen\n"
        "8-9: Strong answer with minor improvements possible\n"
        "10: Exceptional, comprehensive answer"
    ),
    "Data Analyst": (
        "1-3: Missing basic SQL, no metric understanding\n"
        "4-5: Basic query works but inefficient, vague metrics\n"
        "6-7: Correct SQL, decent metric reasoning\n"
        "8-9: Optimized queries, clear business logic, good communication\n"
        "10: Production-quality SQL, deep business insight, stakeholder-ready"
    ),
    "Data Engineer": (
        "1-3: No pipeline awareness, broken SQL, missing fundamentals\n"
        "4-5: Basic design but ignores scale, fault tolerance, monitoring\n"
        "6-7: Solid architecture, correct trade-offs, some edge-case gaps\n"
        "8-9: Production-grade design, clear scalability reasoning\n"
        "10: Handles all edge cases, optimal tech choices, monitoring + alerting"
    ),
}

_EVALUATION_PROMPT = """You are a senior {role} interviewer at {company}.

ROUND: {round_name}
QUESTION: {question}
SKILLS TESTED: {skills_tested}
EXPERIENCE: {experience_level}

CANDIDATE'S ANSWER:
{user_answer}

Evaluate thoroughly. Return JSON:
- "score": 1-10
- "strengths": [2-4 items]
- "gaps": [2-4 items]
- "ideal_answer": concise model answer (3-5 sentences)
- "skills_to_improve": [specific skills]
- "next_steps": [2-3 actionable suggestions]

Scoring guide:
{scoring_guide}
"""

_REASONING_PROMPT = """Company: {company} | Role: {role}
Round: {round_name} (Round {round_order}) | Skills: {skills}

In 2-3 sentences explain:
1. WHY {company} asks this in the {round_name} round
2. WHY these skills matter for a {role} at {company}
3. HOW this connects to {company}'s culture

Be specific — reference products, data challenges, or known practices.
Return plain text."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def _call_openai_json(client: OpenAI, system: str, user: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise LLMError("Empty response from GPT")
    return json.loads(raw)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def _call_openai_text(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    return (response.choices[0].message.content or "").strip()


def evaluate_answer(
    company: str,
    question: str,
    user_answer: str,
    kg_context: dict,
    round_name: str = "",
    experience_level: str = "Mid",
    role: str = "Data Scientist",
) -> dict:
    """Evaluate a candidate answer; returns validated EvaluationResult dict."""
    from config import get_settings

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    skills: list[str] = []
    if kg_context.get("round_details") and kg_context["round_details"].get("skills"):
        skills = [s["skill"] for s in kg_context["round_details"]["skills"]]
    if not skills:
        skills = [s["name"] for s in kg_context.get("skills", [])[:5]]

    resources = kg_context.get("resources", {})
    resource_list = [
        f"{r['name']} ({r.get('url', 'N/A')}) — for {sk}"
        for sk, rs in resources.items()
        for r in rs
    ]

    scoring_guide = _SCORING_GUIDES.get(role, _SCORING_GUIDES["Data Scientist"])

    prompt = _EVALUATION_PROMPT.format(
        company=company,
        role=role,
        round_name=round_name or "General",
        question=question,
        skills_tested=", ".join(skills) or "General",
        experience_level=experience_level,
        user_answer=user_answer,
        scoring_guide=scoring_guide,
    )

    logger.debug("Evaluating answer for %s / %s", company, role)
    raw = _call_openai_json(client, f"You are an expert {role} interviewer at {company}.", prompt)

    result = EvaluationResult.model_validate(raw)
    out = result.model_dump()
    out["recommended_resources"] = resource_list[:6]
    return out


def explain_reasoning_path(
    company: str,
    round_name: str,
    round_order: int,
    skills: list[str],
    role: str = "Data Scientist",
) -> str:
    """Explain WHY the company tests these skills in this round."""
    from config import get_settings

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    prompt = _REASONING_PROMPT.format(
        company=company,
        role=role,
        round_name=round_name,
        round_order=round_order,
        skills=", ".join(skills) or "General",
    )
    return _call_openai_text(client, prompt)
