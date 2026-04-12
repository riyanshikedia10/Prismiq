"""
Knowledge Graph loader — builds the KG entirely from REAL, verified data sources.
No GPT-generated content. GPT is used only at runtime (generator + evaluator).

Data sources loaded:
  1. Seed round structures (hand-verified from Glassdoor/Blind) — llm/seeds.py
  2. LeetCode problems (GitHub CSVs) — data/processed/{slug}_leetcode_{company}.json
  3. Kaggle job skills (12K+944 postings) — data/processed/job_market_skills.json
  4. GitHub interview questions (3 repos, 2400+ Qs) — data/processed/github_{ds,de}_questions.json
  5. Curated learning resources (50 real URLs) — data/resources.py
"""

from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neo4j import Driver

from kg.schema import get_driver, setup_schema, verify_connectivity, clear_database
from config import ROLES, ROLE_SLUGS, COMPANIES, EXPERIENCE_LEVELS, setup_logging
from llm.seeds import SEED_DATA
from data.resources import RESOURCES

logger = logging.getLogger(__name__)

MIN_SKILL_FREQ = 10


# ── 1. Foundation nodes ──────────────────────────────────────────────────────

def _load_foundation(session) -> None:
    session.run("UNWIND $levels AS lv MERGE (el:ExperienceLevel {level: lv})", levels=EXPERIENCE_LEVELS)
    session.run("UNWIND $roles AS r MERGE (role:Role {name: r})", roles=ROLES)
    session.run("UNWIND $cos AS c MERGE (co:Company {name: c})", cos=COMPANIES)
    logger.info("[Foundation] %d levels, %d roles, %d companies", len(EXPERIENCE_LEVELS), len(ROLES), len(COMPANIES))


# ── 2. Seed round structures (from Glassdoor/Blind — real data) ──────────────

def _load_seed_rounds(session) -> None:
    total = 0
    for role, companies in SEED_DATA.items():
        slug = ROLE_SLUGS[role]
        for company, data in companies.items():
            for rnd in data["rounds"]:
                round_id = f"{company}_{slug}_{rnd['name']}".replace(" ", "_")
                session.run(
                    """
                    MERGE (ir:InterviewRound {id: $id})
                      ON CREATE SET ir.name = $name, ir.order = $order,
                                    ir.duration_min = $dur,
                                    ir.question_types = $qtypes,
                                    ir.skills_tested = $skills,
                                    ir.role = $role, ir.source = 'glassdoor/blind'
                    WITH ir
                    MATCH (c:Company {name: $company})
                    MERGE (c)-[hr:HAS_ROUND]->(ir) SET hr.order = $order, hr.role = $role
                    """,
                    id=round_id, name=rnd["name"], order=rnd["order"],
                    dur=rnd.get("duration_min", 45),
                    qtypes=rnd.get("question_types", []),
                    skills=rnd.get("skills_tested", []),
                    role=role, company=company,
                )
                total += 1
    logger.info("[Seed Rounds] %d rounds loaded (source: Glassdoor/Blind)", total)


# ── 3. LeetCode problems ────────────────────────────────────────────────────

def _load_leetcode(session) -> None:
    total = 0
    for role in ROLES:
        slug = ROLE_SLUGS[role]
        for company in COMPANIES:
            path = f"data/processed/{slug}_leetcode_{company.lower()}.json"
            if not os.path.exists(path):
                continue
            with open(path) as f:
                data = json.load(f)

            prefix = f"{company}_{slug}"
            for q in data.get("questions", []):
                q_id = q.get("id", f"{prefix}_LC{total}")
                round_name = q.get("round", "Technical Screen")
                round_id = f"{prefix}_{round_name}".replace(" ", "_")

                session.run(
                    """
                    MERGE (iq:InterviewQuestion {id: $id})
                      ON CREATE SET iq.text = $text, iq.difficulty = $diff,
                                    iq.round_name = $rname, iq.source = $src,
                                    iq.source_url = $url, iq.acceptance = $acc,
                                    iq.role = $role
                    """,
                    id=q_id, text=q["text"], diff=q.get("difficulty", "Medium"),
                    rname=round_name, src="leetcode",
                    url=q.get("source_url", ""), acc=q.get("acceptance", ""),
                    role=role,
                )
                session.run(
                    "MATCH (ir:InterviewRound {id: $rid}), (iq:InterviewQuestion {id: $qid}) MERGE (ir)-[:CONTAINS]->(iq)",
                    rid=round_id, qid=q_id,
                )
                for sk in q.get("skills_tested", []):
                    session.run("MERGE (s:Skill {name: $s})", s=sk)
                    session.run(
                        "MATCH (iq:InterviewQuestion {id: $qid}), (s:Skill {name: $s}) MERGE (iq)-[:TESTS]->(s)",
                        qid=q_id, s=sk,
                    )
                for lv in q.get("experience_levels", EXPERIENCE_LEVELS):
                    session.run(
                        "MATCH (iq:InterviewQuestion {id: $qid}), (el:ExperienceLevel {level: $lv}) MERGE (iq)-[:FOR_LEVEL]->(el)",
                        qid=q_id, lv=lv,
                    )
                total += 1

    logger.info("[LeetCode] %d problems loaded (source: GitHub CSV)", total)


# ── 4. Kaggle job market skills ──────────────────────────────────────────────

def _load_job_market_skills(session) -> None:
    path = "data/processed/job_market_skills.json"
    if not os.path.exists(path):
        logger.warning("[Kaggle Skills] %s not found — skipping", path)
        return

    with open(path) as f:
        data = json.load(f)

    total = 0
    for role, skills in data.items():
        filtered = [s for s in skills if s.get("frequency", 0) >= MIN_SKILL_FREQ]
        for skill in filtered:
            session.run(
                "MERGE (s:Skill {name: $name}) ON CREATE SET s.category = 'Technical', s.source = 'kaggle'",
                name=skill["name"],
            )
            session.run(
                "MATCH (r:Role {name: $role}), (s:Skill {name: $sk}) MERGE (r)-[:NEEDS]->(s)",
                role=role, sk=skill["name"],
            )
            for co in skill.get("companies", []):
                if co in COMPANIES:
                    session.run(
                        """
                        MATCH (c:Company {name: $co}), (s:Skill {name: $sk})
                        MERGE (c)-[r:REQUIRES {role: $role}]->(s)
                          ON CREATE SET r.importance = $imp, r.source = 'kaggle'
                        """,
                        co=co, sk=skill["name"], role=role, imp=skill["importance"],
                    )
            total += 1

    logger.info("[Kaggle Skills] %d skills loaded (freq >= %d, source: Kaggle job postings)", total, MIN_SKILL_FREQ)


# ── 5. GitHub interview questions ────────────────────────────────────────────

def _load_github_questions(session) -> None:
    files = {
        "data/processed/github_ds_questions.json": "Data Scientist",
        "data/processed/github_de_questions.json": "Data Engineer",
    }
    total = 0
    for path, default_role in files.items():
        if not os.path.exists(path):
            logger.warning("[GitHub Qs] %s not found — skipping", path)
            continue
        with open(path) as f:
            questions = json.load(f)

        slug = ROLE_SLUGS[default_role]
        for i, q in enumerate(questions):
            q_id = f"GH_{slug}_{i + 1}"
            role = q.get("role", default_role)
            topic = q.get("topic", "General")

            session.run(
                """
                MERGE (iq:InterviewQuestion {id: $id})
                  ON CREATE SET iq.text = $text, iq.difficulty = $diff,
                                iq.round_name = $rname, iq.source = $src,
                                iq.role = $role, iq.topic = $topic
                """,
                id=q_id, text=q["text"], diff=q.get("difficulty", "Medium"),
                rname=q.get("round", "Technical Screen"),
                src=q.get("source", "github"), role=role, topic=topic,
            )
            for sk in q.get("skills_tested", []):
                session.run("MERGE (s:Skill {name: $s})", s=sk)
                session.run(
                    "MATCH (iq:InterviewQuestion {id: $qid}), (s:Skill {name: $s}) MERGE (iq)-[:TESTS]->(s)",
                    qid=q_id, s=sk,
                )
            for lv in q.get("experience_levels", EXPERIENCE_LEVELS):
                session.run(
                    "MATCH (iq:InterviewQuestion {id: $qid}), (el:ExperienceLevel {level: $lv}) MERGE (iq)-[:FOR_LEVEL]->(el)",
                    qid=q_id, lv=lv,
                )
            total += 1

    logger.info("[GitHub Qs] %d questions loaded (source: curated GitHub repos)", total)


# ── 6. Curated learning resources ────────────────────────────────────────────

def _load_resources(session) -> None:
    for i, res in enumerate(RESOURCES):
        res_id = f"RES_{i + 1}"
        session.run(
            """
            MERGE (lr:LearningResource {id: $id})
              ON CREATE SET lr.name = $name, lr.url = $url, lr.type = $type, lr.source = 'curated'
            """,
            id=res_id, name=res["name"], url=res["url"], type=res["type"],
        )
        session.run("MERGE (s:Skill {name: $s})", s=res["skill"])
        session.run(
            "MATCH (s:Skill {name: $s}), (lr:LearningResource {id: $rid}) MERGE (s)-[:HAS_RESOURCE]->(lr)",
            s=res["skill"], rid=res_id,
        )
    logger.info("[Resources] %d curated resources loaded (real URLs)", len(RESOURCES))


# ── Main ─────────────────────────────────────────────────────────────────────

def load_all(driver: Driver) -> None:
    """Load all real data into Neo4j. Zero GPT content."""
    with driver.session() as session:
        _load_foundation(session)
        _load_seed_rounds(session)
        _load_leetcode(session)
        _load_job_market_skills(session)
        _load_github_questions(session)
        _load_resources(session)

    with driver.session() as session:
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        logger.info("=" * 50)
        logger.info("TOTAL: %d nodes, %d relationships", nodes, rels)
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC"
        )
        for rec in result:
            logger.info("  %s: %d", rec["label"], rec["cnt"])
        logger.info("=" * 50)
        logger.info("ALL DATA FROM REAL SOURCES — zero GPT content in KG")


if __name__ == "__main__":
    setup_logging()
    driver = get_driver()
    try:
        verify_connectivity(driver)
        logger.info("Clearing old data...")
        clear_database(driver)
        setup_schema(driver)
        load_all(driver)
    finally:
        driver.close()
