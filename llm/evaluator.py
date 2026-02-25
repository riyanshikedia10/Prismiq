"""
Answer evaluation and reasoning path explanation using GPT-4o-mini.
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EVALUATION_PROMPT = """You are a senior Data Scientist interviewer at {company}.

INTERVIEW ROUND: {round_name}
QUESTION: {question}
SKILLS BEING TESTED: {skills_tested}
EXPERIENCE LEVEL: {experience_level}

CANDIDATE'S ANSWER:
{user_answer}

Evaluate the candidate's answer thoroughly. Return your evaluation as JSON with these keys:

- "score": integer from 1 to 10
- "strengths": list of 2-4 specific things the candidate did well
- "gaps": list of 2-4 specific things the candidate missed or could improve
- "ideal_answer": a concise model answer (3-5 sentences) showing what a strong response looks like
- "skills_to_improve": list of specific skills the candidate should work on
- "next_steps": 2-3 actionable suggestions for improvement

Scoring guide:
- 1-3: Major gaps, missing core concepts
- 4-5: Partial understanding, significant gaps
- 6-7: Good grasp, some areas to strengthen
- 8-9: Strong answer with minor improvements possible
- 10: Exceptional, comprehensive answer
"""

REASONING_PROMPT = """The Knowledge Graph for interview preparation shows this path:

Company: {company}
Interview Round: {round_name} (Round {round_order})
Question tests: {skills}

Explain to the candidate in 2-3 concise sentences:
1. WHY {company} asks this type of question in the {round_name} round
2. WHY these skills ({skills}) are important for a Data Scientist at {company}
3. HOW this connects to {company}'s interview philosophy and culture

Be specific to {company} — reference their products, culture, or known practices where relevant.
Return plain text, not JSON.
"""


def evaluate_answer(
    company: str,
    question: str,
    user_answer: str,
    kg_context: dict,
    round_name: str = "",
    experience_level: str = "Mid",
) -> dict:
    """
    Evaluate a user's answer to an interview question.

    Returns:
        dict with score, strengths, gaps, ideal_answer, skills_to_improve, next_steps
    """
    # Extract skills being tested
    skills = []
    if kg_context.get("round_details") and kg_context["round_details"].get("skills"):
        skills = [s["skill"] for s in kg_context["round_details"]["skills"]]
    if not skills:
        skills = [s["name"] for s in kg_context.get("skills", [])[:5]]

    # Gather relevant resources from KG context
    resources = kg_context.get("resources", {})
    resource_list = []
    for skill_name, skill_resources in resources.items():
        for r in skill_resources:
            resource_list.append(f"{r['name']} ({r.get('url', 'N/A')}) — for {skill_name}")

    prompt = EVALUATION_PROMPT.format(
        company=company,
        round_name=round_name or "General",
        question=question,
        skills_tested=", ".join(skills),
        experience_level=experience_level,
        user_answer=user_answer,
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are an expert interviewer at {company}."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    result = json.loads(response.choices[0].message.content)

    result.setdefault("score", 5)
    result.setdefault("strengths", [])
    result.setdefault("gaps", [])
    result.setdefault("ideal_answer", "")
    result.setdefault("skills_to_improve", [])
    result.setdefault("next_steps", [])

    # Attach KG resources for recommended skills
    result["recommended_resources"] = resource_list[:6]

    return result


def explain_reasoning_path(
    company: str,
    round_name: str,
    round_order: int,
    skills: list,
) -> str:
    """
    Takes KG path info and returns a natural-language explanation
    of WHY the company tests these skills in this round.
    """
    prompt = REASONING_PROMPT.format(
        company=company,
        round_name=round_name,
        round_order=round_order,
        skills=", ".join(skills),
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    return response.choices[0].message.content.strip()
