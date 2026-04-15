"""
Knowledge Graph loader — builds the KG entirely from REAL, verified data sources.
No GPT-generated content. GPT is used only at runtime (generator + evaluator).

Data sources loaded:
  1. Seed round structures (hand-verified from Glassdoor/Blind) — llm/seeds.py
  2. LeetCode problems (GitHub CSVs) — data/processed/{slug}_leetcode_{company}.json
  3. Kaggle job skills (allowlisted technical skills only) — data/processed/job_market_skills.json
  4. GitHub interview questions — data/processed/github_{ds,de}_questions.json
  5. Curated learning resources — data/resources.py

Skill importance hierarchy:
  - Critical: company+role specific tech stack (from CRITICAL_BY_COMPANY_ROLE)
  - Medium:   appears in 1 round, or is a soft/behavioral skill
  - Kaggle:   only adds Skill nodes via Role-level NEEDS, never Company-level
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


# ── Skill classification ──────────────────────────────────────────────────────

# Soft/behavioral skills — always Medium regardless of company or role
SOFT_SKILLS = {
    "Communication", "Leadership", "Teamwork", "Culture Fit",
    "Autonomy", "Ownership", "Impact", "Collaboration",
    "Growth Mindset", "Innovation", "Speed", "Background",
    "Motivation", "Leadership Principles", "Googleyness",
    "Bar Raiser", "Business Sense", "Domain Expertise",
    "Product", "Stakeholder Communication", "Freedom & Responsibility",
}

# Critical skills per (company, role) — reflects actual tech stack
CRITICAL_BY_COMPANY_ROLE: dict[tuple[str, str], set[str]] = {
    # ── Data Engineer ─────────────────────────────────────────────────────────
    ("Google", "Data Engineer"): {
        "SQL", "Python", "Distributed Systems", "Data Pipelines",
        "Data Modeling", "Schema Design", "Data Structures",
    },
    ("Amazon", "Data Engineer"): {
        "SQL", "Python", "AWS", "Data Pipelines",
        "Distributed Systems", "Data Modeling", "Redshift",
    },
    ("Meta", "Data Engineer"): {
        "SQL", "Python", "Data Pipelines", "Distributed Systems",
        "Streaming", "Algorithms",
    },
    ("Apple", "Data Engineer"): {
        "SQL", "Python", "Spark", "Data Pipelines",
        "Data Modeling", "Cloud",
    },
    ("Netflix", "Data Engineer"): {
        "SQL", "Python", "Spark", "Kafka",
        "Distributed Systems", "Data Architecture", "Data Modeling",
    },
    ("Microsoft", "Data Engineer"): {
        "SQL", "Python", "Azure", "Data Pipelines",
        "Distributed Systems", "Data Modeling",
    },
    ("Tesla", "Data Engineer"): {
        "SQL", "Python", "Spark", "Airflow",
        "Data Pipelines", "Streaming", "IoT Data", "Data Modeling",
    },
    ("TikTok", "Data Engineer"): {
        "SQL", "Python", "Spark", "Kafka",
        "Distributed Systems", "Streaming", "Algorithms",
    },
    ("Uber", "Data Engineer"): {
        "SQL", "Python", "Kafka", "Spark",
        "Data Pipelines", "Data Modeling",
    },
    # ── Data Scientist ────────────────────────────────────────────────────────
    ("Google", "Data Scientist"): {
        "SQL", "Python", "Statistics", "Machine Learning",
        "A/B Testing", "Probability",
    },
    ("Amazon", "Data Scientist"): {
        "SQL", "Python", "Machine Learning", "A/B Testing",
        "Advanced SQL", "Business Metrics",
    },
    ("Meta", "Data Scientist"): {
        "SQL", "Statistics", "A/B Testing", "Causal Inference",
        "Probability", "Metrics",
    },
    ("Apple", "Data Scientist"): {
        "SQL", "Python", "Machine Learning", "Statistics",
        "Statistical Modeling",
    },
    ("Netflix", "Data Scientist"): {
        "SQL", "Statistics", "A/B Testing", "Causal Inference",
        "Behavioral Data", "Product Metrics",
    },
    ("Microsoft", "Data Scientist"): {
        "SQL", "Python", "Machine Learning", "Statistics",
        "Experimentation",
    },
    ("Tesla", "Data Scientist"): {
        "Python", "SQL", "Machine Learning", "Deep Learning",
        "Statistics", "Sensor Data",
    },
    ("TikTok", "Data Scientist"): {
        "SQL", "Python", "Machine Learning", "Recommender Systems",
        "A/B Testing", "Algorithms",
    },
    ("Uber", "Data Scientist"): {
        "SQL", "Python", "Statistics", "A/B Testing",
        "Causal Inference",
    },
    # ── Data Analyst ──────────────────────────────────────────────────────────
    ("Google", "Data Analyst"): {
        "SQL", "Statistics", "A/B Testing",
        "Product Metrics", "Data Cleaning",
    },
    ("Amazon", "Data Analyst"): {
        "SQL", "Advanced SQL", "Excel", "Business Metrics",
        "Tableau", "A/B Testing",
    },
    ("Meta", "Data Analyst"): {
        "SQL", "Metrics", "A/B Testing",
        "Product Analytics", "Data Interpretation",
    },
    ("Apple", "Data Analyst"): {
        "SQL", "Excel", "Tableau", "Statistics",
        "Business Analysis",
    },
    ("Netflix", "Data Analyst"): {
        "SQL", "Excel", "A/B Testing", "Metrics",
        "Visualization", "Behavioral Data",
    },
    ("Microsoft", "Data Analyst"): {
        "SQL", "Excel", "Power BI", "Business Metrics",
        "Statistics",
    },
    ("Tesla", "Data Analyst"): {
        "SQL", "Excel", "Business Metrics",
        "Visualization", "Data Cleaning",
    },
    ("TikTok", "Data Analyst"): {
        "SQL", "Excel", "Product Metrics",
        "A/B Testing", "Visualization",
    },
    ("Uber", "Data Analyst"): {
        "SQL", "Excel", "Business Metrics",
        "A/B Testing", "Visualization",
    },
}

# Kaggle allowlist — only well-known technical skills are trusted from job postings
KAGGLE_TECHNICAL_ALLOWLIST = {
    "Python", "SQL", "R", "Scala", "Java",
    "Spark", "Kafka", "Airflow", "dbt", "Flink",
    "Tableau", "Power BI", "Looker", "Excel",
    "AWS", "GCP", "Azure", "Snowflake", "Databricks",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Machine Learning", "Deep Learning", "Statistics",
    "A/B Testing", "Data Modeling", "Data Pipelines",
    "Kubernetes", "Docker", "Redshift", "BigQuery",
    "Data Visualization", "SAS", "Matlab",
}

# Topic to round name mapping (must match seed round names exactly)
TOPIC_TO_ROUND: dict[str, str] = {
    "Machine Learning":  "Onsite: Stats & ML",
    "Deep Learning":     "Onsite: Stats & ML",
    "Statistics":        "Onsite: Stats & ML",
    "Probability":       "Onsite: Stats & ML",
    "Apache Spark":      "Onsite: Coding & Pipelines",
    "Kafka":             "Onsite: Coding & Pipelines",
    "Hadoop":            "Onsite: Coding & Pipelines",
    "Hive":              "Onsite: Coding & Pipelines",
    "Apache Flink":      "Onsite: Coding & Pipelines",
    "Apache NiFi":       "Onsite: System Design",
    "Apache Hudi":       "Onsite: System Design",
    "Apache Iceberg":    "Onsite: System Design",
    "Airflow":           "Onsite: System Design",
    "Data Modeling":     "Onsite: Data Modeling",
    "Data Warehousing":  "Onsite: Data Modeling",
    "Redshift":          "Onsite: Data Modeling",
    "BigQuery":          "Onsite: Data Modeling",
    "System Design":     "Onsite: System Design",
    "AWS":               "Onsite: System Design",
    "GCP":               "Onsite: System Design",
    "Azure":             "Onsite: System Design",
    "Docker":            "Onsite: Coding",
    "Kubernetes":        "Onsite: System Design",
    "Data Quality":      "Onsite: System Design",
    "Data Governance":   "Onsite: System Design",
    "Delta Lake":        "Onsite: System Design",
    "CDC":               "Onsite: System Design",
    "HBase":             "Onsite: System Design",
    "Cassandra":         "Onsite: System Design",
    "MongoDB":           "Onsite: System Design",
    "Observability":     "Onsite: System Design",
    "Cost Optimization": "Onsite: System Design",
    "Impala":            "Onsite: Coding & Pipelines",
    "Flume":             "Onsite: Coding & Pipelines",
    "SQL":               "Technical Screen",
    "Python":            "Technical Screen",
    "dbt":               "Technical Screen",
    "Parquet":           "Technical Screen",
    "Avro":              "Technical Screen",
    "Data Structures":   "Onsite: Coding",
    "General":           "Technical Screen",
}

# Experience level derived from question difficulty
DIFFICULTY_TO_LEVEL: dict[str, str] = {
    "Easy":   "Entry",
    "Medium": "Mid",
    "Hard":   "Senior",
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_importance(skill: str, company: str, role: str, freq: int) -> str:
    """Derive skill importance from company+role tech stack and round frequency."""
    if skill in SOFT_SKILLS:
        return "Medium"
    if skill in CRITICAL_BY_COMPANY_ROLE.get((company, role), set()):
        return "Critical"
    return "High" if freq >= 2 else "Medium"


# ── 1. Foundation nodes ───────────────────────────────────────────────────────

def _load_foundation(session) -> None:
    session.run(
        "UNWIND $levels AS lv MERGE (el:ExperienceLevel {level: lv})",
        levels=EXPERIENCE_LEVELS,
    )
    session.run(
        "UNWIND $roles AS r MERGE (role:Role {name: r})",
        roles=ROLES,
    )
    session.run(
        "UNWIND $cos AS c MERGE (co:Company {name: c})",
        cos=COMPANIES,
    )
    logger.info(
        "[Foundation] %d levels, %d roles, %d companies",
        len(EXPERIENCE_LEVELS), len(ROLES), len(COMPANIES),
    )


# ── 2. Seed rounds + NEEDS relationships ──────────────────────────────────────

def _load_seed_rounds(session) -> None:
    total_rounds = 0
    total_needs  = 0

    for role, companies in SEED_DATA.items():
        slug = ROLE_SLUGS[role]
        for company, data in companies.items():

            # Count skill frequency across rounds for this company+role
            skill_freq: dict[str, int] = {}
            for rnd in data["rounds"]:
                for sk in rnd.get("skills_tested", []):
                    skill_freq[sk] = skill_freq.get(sk, 0) + 1

            for rnd in data["rounds"]:
                round_id = f"{company}_{slug}_{rnd['name']}".replace(" ", "_")
                session.run(
                    """
                    MERGE (ir:InterviewRound {id: $id})
                      ON CREATE SET ir.name           = $name,
                                    ir.order          = $order,
                                    ir.duration_min   = $dur,
                                    ir.question_types = $qtypes,
                                    ir.skills_tested  = $skills,
                                    ir.role           = $role,
                                    ir.source         = 'glassdoor/blind'
                    WITH ir
                    MATCH (c:Company {name: $company})
                    MERGE (c)-[hr:HAS_ROUND]->(ir)
                      SET hr.order = $order, hr.role = $role
                    """,
                    id=round_id,
                    name=rnd["name"],
                    order=rnd["order"],
                    dur=rnd.get("duration_min", 45),
                    qtypes=rnd.get("question_types", []),
                    skills=rnd.get("skills_tested", []),
                    role=role,
                    company=company,
                )
                total_rounds += 1

                for sk in rnd.get("skills_tested", []):
                    freq       = skill_freq.get(sk, 1)
                    importance = _get_importance(sk, company, role, freq)

                    session.run("MERGE (s:Skill {name: $s})", s=sk)
                    session.run(
                        """
                        MATCH (c:Company {name: $co}), (s:Skill {name: $sk})
                        MERGE (c)-[r:NEEDS {role: $role}]->(s)
                        ON CREATE SET r.importance = $imp, r.source = 'seed'
                        ON MATCH SET r.importance = CASE
                            WHEN $imp = 'Critical' THEN 'Critical'
                            WHEN r.importance <> 'Critical' AND $imp = 'High' THEN 'High'
                            ELSE r.importance
                        END
                        """,
                        co=company, sk=sk, role=role, imp=importance,
                    )
                    total_needs += 1

    logger.info(
        "[Seed Rounds] %d rounds, %d NEEDS relationships (source: Glassdoor/Blind)",
        total_rounds, total_needs,
    )


# ── 3. LeetCode problems ──────────────────────────────────────────────────────

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
                q_id       = q.get("id", f"{prefix}_LC{total}")
                round_name = q.get("round", "Technical Screen")
                round_id   = f"{prefix}_{round_name}".replace(" ", "_")

                session.run(
                    """
                    MERGE (iq:InterviewQuestion {id: $id})
                      ON CREATE SET iq.text       = $text,
                                    iq.difficulty = $diff,
                                    iq.round_name = $rname,
                                    iq.source     = $src,
                                    iq.source_url = $url,
                                    iq.acceptance = $acc,
                                    iq.role       = $role
                    """,
                    id=q_id, text=q["text"], diff=q.get("difficulty", "Medium"),
                    rname=round_name, src="leetcode",
                    url=q.get("source_url", ""), acc=q.get("acceptance", ""),
                    role=role,
                )
                session.run(
                    """
                    MATCH (ir:InterviewRound {id: $rid}), (iq:InterviewQuestion {id: $qid})
                    MERGE (ir)-[:CONTAINS]->(iq)
                    """,
                    rid=round_id, qid=q_id,
                )
                for sk in q.get("skills_tested", []):
                    session.run("MERGE (s:Skill {name: $s})", s=sk)
                    session.run(
                        """
                        MATCH (iq:InterviewQuestion {id: $qid}), (s:Skill {name: $s})
                        MERGE (iq)-[:TESTS]->(s)
                        """,
                        qid=q_id, s=sk,
                    )
                for lv in q.get("experience_levels", EXPERIENCE_LEVELS):
                    session.run(
                        """
                        MATCH (iq:InterviewQuestion {id: $qid}), (el:ExperienceLevel {level: $lv})
                        MERGE (iq)-[:FOR_LEVEL]->(el)
                        """,
                        qid=q_id, lv=lv,
                    )
                total += 1

    logger.info("[LeetCode] %d problems loaded (source: GitHub CSV)", total)


# ── 4. Kaggle job market skills (allowlisted technical only) ──────────────────

def _load_job_market_skills(session) -> None:
    path = "data/processed/job_market_skills.json"
    if not os.path.exists(path):
        logger.warning("[Kaggle Skills] %s not found — skipping", path)
        return

    with open(path) as f:
        data = json.load(f)

    total   = 0
    skipped = 0

    for role, skills in data.items():
        seen_skills: set[str] = set()
        for skill in skills:
            skill_name = skill["name"].strip()

            # Only load skills in the technical allowlist — skip all noise
            if skill_name not in KAGGLE_TECHNICAL_ALLOWLIST:
                skipped += 1
                continue

            # Deduplicate within role
            if skill_name in seen_skills:
                continue
            seen_skills.add(skill_name)

            # Create Skill node
            session.run(
                """
                MERGE (s:Skill {name: $name})
                ON CREATE SET s.category = 'Technical', s.source = 'kaggle'
                """,
                name=skill_name,
            )

            # Link to Role only — seed data owns Company-level NEEDS
            session.run(
                """
                MATCH (r:Role {name: $role}), (s:Skill {name: $sk})
                MERGE (r)-[:NEEDS]->(s)
                """,
                role=role, sk=skill_name,
            )
            total += 1

    logger.info(
        "[Kaggle Skills] %d skills loaded, %d skipped (not in technical allowlist)",
        total, skipped,
    )


# ── 5. GitHub questions → linked to every company's matching round ────────────

def _load_github_questions(session) -> None:
    files = {
        "data/processed/github_ds_questions.json": "Data Scientist",
        "data/processed/github_de_questions.json": "Data Engineer",
    }
    total   = 0
    linked  = 0
    skipped = 0

    for path, default_role in files.items():
        if not os.path.exists(path):
            logger.warning("[GitHub Qs] %s not found — skipping", path)
            continue

        with open(path) as f:
            questions = json.load(f)

        slug = ROLE_SLUGS[default_role]
        for i, q in enumerate(questions):
            q_id  = f"GH_{slug}_{i + 1}"
            role  = q.get("role", default_role)
            topic = q.get("topic", "General")

            session.run(
                """
                MERGE (iq:InterviewQuestion {id: $id})
                  ON CREATE SET iq.text       = $text,
                                iq.difficulty = $diff,
                                iq.round_name = $rname,
                                iq.source     = $src,
                                iq.role       = $role,
                                iq.topic      = $topic
                """,
                id=q_id, text=q["text"], diff=q.get("difficulty", "Medium"),
                rname=q.get("round", "Technical Screen"),
                src=q.get("source", "github"), role=role, topic=topic,
            )

            for sk in q.get("skills_tested", []):
                session.run("MERGE (s:Skill {name: $s})", s=sk)
                session.run(
                    """
                    MATCH (iq:InterviewQuestion {id: $qid}), (s:Skill {name: $s})
                    MERGE (iq)-[:TESTS]->(s)
                    """,
                    qid=q_id, s=sk,
                )

            # Map difficulty to experience level
            level = DIFFICULTY_TO_LEVEL.get(q.get("difficulty", "Medium"), "Mid")
            session.run(
                """
                MATCH (iq:InterviewQuestion {id: $qid}), (el:ExperienceLevel {level: $lv})
                MERGE (iq)-[:FOR_LEVEL]->(el)
                """,
                qid=q_id, lv=level,
            )

            # Link question to matching round in every company
            round_suffix = TOPIC_TO_ROUND.get(topic, "Technical Screen")
            for company in COMPANIES:
                round_id = f"{company}_{slug}_{round_suffix}".replace(" ", "_")
                result = session.run(
                    """
                    MATCH (ir:InterviewRound {id: $rid}), (iq:InterviewQuestion {id: $qid})
                    MERGE (ir)-[:CONTAINS]->(iq)
                    RETURN count(*) AS c
                    """,
                    rid=round_id, qid=q_id,
                ).single()
                if result and result["c"] > 0:
                    linked += 1
                else:
                    skipped += 1

            total += 1

    logger.info(
        "[GitHub Qs] %d questions, %d company-round links, %d skipped (no matching round)",
        total, linked, skipped,
    )


# ── 6. Curated learning resources ─────────────────────────────────────────────

def _load_resources(session) -> None:
    for i, res in enumerate(RESOURCES):
        res_id = f"RES_{i + 1}"
        session.run(
            """
            MERGE (lr:LearningResource {id: $id})
              ON CREATE SET lr.name   = $name,
                            lr.url    = $url,
                            lr.type   = $type,
                            lr.source = 'curated'
            """,
            id=res_id, name=res["name"], url=res["url"], type=res["type"],
        )
        session.run("MERGE (s:Skill {name: $s})", s=res["skill"])
        session.run(
            """
            MATCH (s:Skill {name: $s}), (lr:LearningResource {id: $rid})
            MERGE (s)-[:HAS_RESOURCE]->(lr)
            """,
            s=res["skill"], rid=res_id,
        )
    logger.info("[Resources] %d curated resources loaded (real URLs)", len(RESOURCES))


# ── Main ──────────────────────────────────────────────────────────────────────

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
        rels  = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        logger.info("=" * 50)
        logger.info("TOTAL: %d nodes, %d relationships", nodes, rels)

        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC"
        )
        for rec in result:
            logger.info("  %s: %d", rec["label"], rec["cnt"])

        # Verify per role — all companies, no hardcoding
        for role in ROLES:
            logger.info("-" * 40)
            logger.info("Role: %s", role)

            q_counts = session.run(
                """
                MATCH (c:Company)-[:HAS_ROUND]->(r:InterviewRound)
                      -[:CONTAINS]->(q:InterviewQuestion)
                WHERE r.role = $role
                RETURN c.name AS company, count(q) AS questions
                ORDER BY questions DESC
                """,
                role=role,
            )
            for rec in q_counts:
                logger.info("  %s: %d questions", rec["company"], rec["questions"])

            skill_counts = session.run(
                """
                MATCH (c:Company)-[n:NEEDS]->(s:Skill)
                WHERE n.role = $role
                RETURN n.importance AS importance, count(s) AS skills
                ORDER BY importance
                """,
                role=role,
            )
            for rec in skill_counts:
                logger.info("  Skills %s: %d", rec["importance"], rec["skills"])

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
