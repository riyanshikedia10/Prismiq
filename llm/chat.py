"""
LLM chat layer — synthesizes KG results into natural language answers.
The LLM only formats and explains — all facts come from the KG.
"""

from __future__ import annotations

import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from kg.kg_chat import KGResult
from models import LLMError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are Prismiq, an expert interview preparation assistant.
You answer questions about technical interviews at top tech companies.

CRITICAL RULES:
1. ONLY use the KG data provided — never invent facts, companies, or skills
2. If the KG data is empty, say so clearly — do not make up an answer
3. Always reference specific data points from the KG in your answer
4. Be concise and actionable — candidates need practical advice
5. Never mention GPT, ChatGPT, or AI — you are powered by a Knowledge Graph"""

_ANSWER_PROMPT = """The user asked: "{query}"

Here is the verified data retrieved from the Knowledge Graph:

{kg_context}

Using ONLY this KG data, provide a clear, helpful answer.
- Reference specific facts from the data (round names, skill names, question texts)
- If comparing companies, highlight key differences
- If explaining rounds, mention duration and what's tested
- End with one actionable tip for the candidate
- Keep the answer under 200 words"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _call_llm(client: OpenAI, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=400,
    )
    content = response.choices[0].message.content
    if not content:
        raise LLMError("Empty response from GPT")
    return content.strip()


def _format_kg_context(results: list[KGResult]) -> str:
    """Format KG results into a structured context string for the LLM."""
    parts = []
    for result in results:
        if result.is_empty:
            parts.append(f"[{result.description}]: No data found in KG")
            continue
        parts.append(f"[{result.description}]:")
        for row in result.data:
            line = "  • " + " | ".join(
                f"{k}: {v}" for k, v in row.items() if v is not None
            )
            parts.append(line)
    return "\n".join(parts)


def answer_from_kg(query: str, kg_results: list[KGResult]) -> str:
    """Generate a natural language answer grounded entirely in KG results."""
    from config import get_settings
    settings = get_settings()
    client   = OpenAI(api_key=settings.openai_api_key)

    kg_context  = _format_kg_context(kg_results)
    user_prompt = _ANSWER_PROMPT.format(query=query, kg_context=kg_context)

    logger.debug("Answering chat query: %s", query[:60])
    return _call_llm(client, user_prompt)