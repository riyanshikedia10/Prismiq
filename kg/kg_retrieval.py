"""
Knowledge Graph retrieval functions for the RAG pipeline.
All queries accept a `role` parameter to scope results to the correct
interview rounds, skills, and questions for the selected role.
Uses read transactions for safety.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import Driver

from config import ROLE_SLUGS, EXPERIENCE_LEVELS

logger = logging.getLogger(__name__)


def _prefix(company: str, role: str) -> str:
    """Build round-ID prefix, e.g. 'Google_ds'."""
    return f"{company}_{ROLE_SLUGS.get(role, 'ds')}"


# ── Company overview ─────────────────────────────────────────────────────────

def get_company_overview(driver: Driver, company: str, role: str = "Data Scientist") -> dict[str, Any]:
    pfx = _prefix(company, role)
    with driver.session() as session:
        rounds = [
            dict(r) for r in session.run(
                """
                MATCH (c:Company {name: $co})-[:HAS_ROUND]->(ir:InterviewRound)
                WHERE ir.id STARTS WITH $pfx
                RETURN ir.name AS name, ir.order AS round_order,
                       ir.duration_min AS duration, ir.question_types AS question_types
                ORDER BY ir.order
                """,
                co=company, pfx=pfx,
            )
        ]
        skills = [
            dict(r) for r in session.run(
                """
                MATCH (c:Company {name: $co})-[req:REQUIRES]->(s:Skill)
                WHERE req.role = $role
                RETURN s.name AS name, req.importance AS importance, s.category AS category
                ORDER BY CASE req.importance
                  WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END
                """,
                co=company, role=role,
            )
        ]
    return {"company": company, "role": role, "rounds": rounds, "skills": skills}


# ── Round details ────────────────────────────────────────────────────────────

def get_round_details(
    driver: Driver, company: str, round_name: str, role: str = "Data Scientist",
) -> dict[str, Any]:
    rid = f"{_prefix(company, role)}_{round_name}".replace(" ", "_")
    with driver.session() as session:
        # Get the round's own skills_tested (from seed data)
        round_record = session.run(
            "MATCH (ir:InterviewRound {id: $rid}) RETURN ir.skills_tested AS seed_skills",
            rid=rid,
        ).single()
        seed_skills = (round_record["seed_skills"] or []) if round_record else []

        questions = [
            dict(r) for r in session.run(
                """
                MATCH (ir:InterviewRound {id: $rid})-[:CONTAINS]->(iq:InterviewQuestion)
                OPTIONAL MATCH (iq)-[:TESTS]->(s:Skill)
                RETURN iq.text AS question, iq.difficulty AS difficulty,
                       iq.source AS source, iq.source_url AS source_url,
                       collect(DISTINCT s.name) AS skills_tested
                """,
                rid=rid,
            )
        ]

        # Prefer seed skills; fall back to skills derived from questions
        if seed_skills:
            skills = [{"skill": s, "category": "seed"} for s in seed_skills]
        else:
            skills = [
                dict(r) for r in session.run(
                    """
                    MATCH (ir:InterviewRound {id: $rid})-[:CONTAINS]->(iq)-[:TESTS]->(s:Skill)
                    RETURN DISTINCT s.name AS skill, s.category AS category
                    """,
                    rid=rid,
                )
            ]
    return {"company": company, "role": role, "round": round_name,
            "questions": questions, "skills": skills}


# ── Questions by level ───────────────────────────────────────────────────────

def get_questions_by_level(
    driver: Driver, company: str, experience_level: str, role: str = "Data Scientist",
) -> list[dict[str, Any]]:
    pfx = _prefix(company, role)
    with driver.session() as session:
        return [
            dict(r) for r in session.run(
                """
                MATCH (c:Company {name: $co})-[:HAS_ROUND]->(ir:InterviewRound)
                      -[:CONTAINS]->(iq:InterviewQuestion)-[:FOR_LEVEL]->(el:ExperienceLevel {level: $lv})
                WHERE ir.id STARTS WITH $pfx
                OPTIONAL MATCH (iq)-[:TESTS]->(s:Skill)
                RETURN ir.name AS round_name, ir.order AS round_order,
                       iq.text AS question, iq.difficulty AS difficulty,
                       iq.source AS source, iq.source_url AS source_url,
                       collect(DISTINCT s.name) AS skills_tested
                ORDER BY ir.order
                """,
                co=company, lv=experience_level, pfx=pfx,
            )
        ]


# ── Skill resources ──────────────────────────────────────────────────────────

def get_skill_resources(driver: Driver, skill: str) -> list[dict[str, Any]]:
    with driver.session() as session:
        return [
            dict(r) for r in session.run(
                """
                MATCH (s:Skill {name: $sk})-[:HAS_RESOURCE]->(lr:LearningResource)
                RETURN lr.name AS name, lr.url AS url, lr.type AS type
                """,
                sk=skill,
            )
        ]


# ── Reasoning path ───────────────────────────────────────────────────────────

def get_reasoning_path(driver: Driver, company: str, question_id: str) -> dict[str, Any]:
    with driver.session() as session:
        record = session.run(
            """
            MATCH (c:Company {name: $co})-[:HAS_ROUND]->(ir:InterviewRound)
                  -[:CONTAINS]->(iq:InterviewQuestion {id: $qid})
            OPTIONAL MATCH (iq)-[:TESTS]->(s:Skill)
            OPTIONAL MATCH (s)-[:HAS_RESOURCE]->(lr:LearningResource)
            RETURN c.name AS company, ir.name AS round_name, ir.order AS round_order,
                   iq.text AS question, iq.difficulty AS difficulty,
                   collect(DISTINCT s.name) AS skills,
                   collect(DISTINCT {name: lr.name, url: lr.url}) AS resources
            """,
            co=company, qid=question_id,
        ).single()
        return dict(record) if record else {}


# ── All rounds ───────────────────────────────────────────────────────────────

def get_all_rounds(driver: Driver, company: str, role: str = "Data Scientist") -> list[dict[str, Any]]:
    pfx = _prefix(company, role)
    with driver.session() as session:
        return [
            dict(r) for r in session.run(
                """
                MATCH (c:Company {name: $co})-[:HAS_ROUND]->(ir:InterviewRound)
                WHERE ir.id STARTS WITH $pfx
                RETURN ir.name AS name, ir.order AS round_order
                ORDER BY ir.order
                """,
                co=company, pfx=pfx,
            )
        ]


# ── RAG context assembly ────────────────────────────────────────────────────

def get_context_for_generation(
    driver: Driver,
    company: str,
    role: str,
    experience_level: str,
    round_name: str | None = None,
) -> dict[str, Any]:
    """Main RAG retrieval: full KG context for LLM prompts."""
    overview = get_company_overview(driver, company, role)
    round_details = get_round_details(driver, company, round_name, role) if round_name else None
    level_questions = get_questions_by_level(driver, company, experience_level, role)

    resources: dict[str, list] = {}
    for skill in overview["skills"]:
        if skill["importance"] in ("Critical", "High"):
            sr = get_skill_resources(driver, skill["name"])
            if sr:
                resources[skill["name"]] = sr

    return {
        "company": company,
        "role": role,
        "experience_level": experience_level,
        "rounds": overview["rounds"],
        "skills": overview["skills"],
        "round_details": round_details,
        "sample_questions": level_questions,
        "resources": resources,
    }


# ── Metadata lookups ─────────────────────────────────────────────────────────

def get_companies(driver: Driver) -> list[str]:
    with driver.session() as session:
        return [r["name"] for r in session.run("MATCH (c:Company) RETURN c.name AS name ORDER BY c.name")]


def get_roles(driver: Driver) -> list[str]:
    with driver.session() as session:
        return [r["name"] for r in session.run("MATCH (r:Role) RETURN r.name AS name ORDER BY r.name")]


def get_experience_levels(driver: Driver) -> list[str]:
    with driver.session() as session:
        return [r["level"] for r in session.run("MATCH (el:ExperienceLevel) RETURN el.level AS level ORDER BY el.level")]


def get_companies_for_role(driver: Driver, role: str) -> list[str]:
    with driver.session() as session:
        return [
            r["name"] for r in session.run(
                """
                MATCH (c:Company)-[:HAS_ROUND]->(ir:InterviewRound)
                WHERE ir.role = $role
                RETURN DISTINCT c.name AS name ORDER BY c.name
                """,
                role=role,
            )
        ]
