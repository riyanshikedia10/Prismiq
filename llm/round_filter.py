"""
LLM-based round filtering — uses GPT-4o-mini to determine which interview
rounds from the Knowledge Graph apply to a given experience level.

The KG provides the complete set of rounds (verified from Glassdoor/Blind).
The LLM acts as a filter, using its training knowledge about real interview
processes to decide which rounds a candidate at a given level would face.

No hardcoding — the LLM decides per company, per role, per level.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import LLMError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert on tech company hiring processes. You have deep knowledge "
    "of interview structures at Google, Amazon, Meta, Apple, Netflix, Microsoft, "
    "Tesla, TikTok, and Uber from sources like Glassdoor, Blind, and Levels.fyi."
)

_FILTER_PROMPT = """Given the following interview rounds from our Knowledge Graph for {role} at {company}, determine which rounds a {level}-level candidate would actually go through.

ROUNDS FROM KG:
{rounds_json}

RULES:
- Different companies have DIFFERENT interview structures for entry-level — do NOT assume all companies use the same number of rounds
- Some companies (like Amazon) still require a Bar Raiser for entry-level, others skip it
- Some companies have 3 rounds for entry, some have 4, some have 5 — it depends on the company and role
- Consider {company}'s SPECIFIC and KNOWN hiring practices for {level}-level {role} candidates
- Recruiter Screen always applies
- Think carefully: which of these specific rounds would {company} actually conduct for a {level}-level {role}?
- Base your answer on real interview data from Glassdoor, Blind, and Levels.fyi

Return ONLY a JSON object with this exact format:
{{"selected_rounds": ["Round Name 1", "Round Name 2", ...], "reasoning": "1-2 sentences explaining why these specific rounds for {level} at {company}"}}

The round names MUST exactly match the names provided above. Do not invent new rounds."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _call_openai(client: OpenAI, system: str, user: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise LLMError("Empty response from GPT in round filter")
    return json.loads(raw)


def filter_rounds_by_level(
    company: str,
    role: str,
    experience_level: str,
    rounds: list[dict],
) -> list[dict]:
    """
    Filter KG rounds using GPT-4o-mini to determine which rounds
    apply to the given experience level.

    Args:
        company: e.g. "Google"
        role: e.g. "Data Analyst"
        experience_level: "Entry", "Mid", or "Senior"
        rounds: list of round dicts from KG (must have "name" key)

    Returns:
        Filtered list of round dicts that apply to this level.
        Falls back to all rounds if LLM call fails.
    """
    if not rounds:
        return rounds

    # Mid and Senior always get all rounds — no API call needed
    if experience_level in ("Mid", "Senior"):
        logger.debug("Level=%s -> returning all %d rounds", experience_level, len(rounds))
        return rounds

    from config import get_settings

    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)

        rounds_for_prompt = [
            {
                "name": r["name"],
                "order": r.get("round_order", r.get("order", "?")),
                "duration_min": r.get("duration", r.get("duration_min", "?")),
                "question_types": r.get("question_types", []),
            }
            for r in rounds
        ]

        prompt = _FILTER_PROMPT.format(
            company=company,
            role=role,
            level=experience_level,
            rounds_json=json.dumps(rounds_for_prompt, indent=2),
        )

        logger.debug("Filtering rounds for %s / %s / %s", company, role, experience_level)

        result = _call_openai(client, _SYSTEM_PROMPT, prompt)
        selected_names = set(result.get("selected_rounds", []))
        reasoning = result.get("reasoning", "")

        if not selected_names:
            logger.warning("LLM returned empty selected_rounds — returning all rounds")
            return rounds

        filtered = [r for r in rounds if r["name"] in selected_names]

        if len(filtered) < 2:
            logger.warning("LLM returned only %d rounds — falling back to all", len(filtered))
            return rounds

        actual_names = {r["name"] for r in rounds}
        invalid = selected_names - actual_names
        if invalid:
            logger.warning("LLM returned unknown round names: %s", invalid)

        logger.info(
            "[Round Filter] %s / %s / %s: %d -> %d rounds. Reason: %s",
            company, role, experience_level, len(rounds), len(filtered), reasoning,
        )

        return filtered

    except Exception:
        logger.exception("Round filter LLM call failed — returning all rounds")
        return rounds
