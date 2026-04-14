"""
KG Chat retrieval — every query returns both data AND the exact Cypher that ran.
Pasting the returned Cypher into Neo4j Browser produces identical results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j import Driver


@dataclass
class KGResult:
    """Holds query results + the exact Cypher that produced them."""
    data: list[dict[str, Any]]
    cypher: str
    params: dict[str, Any]
    description: str

    @property
    def runnable_cypher(self) -> str:
        """Returns Cypher with params inlined — paste directly into Neo4j Browser."""
        cypher = self.cypher
        for key, val in self.params.items():
            if isinstance(val, str):
                cypher = cypher.replace(f"${key}", f'"{val}"')
            else:
                cypher = cypher.replace(f"${key}", str(val))
        return cypher.strip()

    @property
    def is_empty(self) -> bool:
        return len(self.data) == 0


# ── Intent detection ──────────────────────────────────────────────────────────

INTENT_KEYWORDS = {
    "rounds":      ["round", "rounds", "stages", "process", "interview process", "steps"],
    "skills":      ["skill", "skills", "require", "need", "tech stack", "tools", "know"],
    "questions":   ["question", "questions", "ask", "asked", "practice", "sample"],
    "compare":     ["compare", "difference", "vs", "versus", "better", "between"],
    "resources":   ["learn", "resource", "study", "prepare", "course", "book", "link"],
    "overview":    ["overview", "about", "tell me", "what is", "how does", "explain"],
}

def detect_intent(query: str) -> str:
    """Detect the primary intent from the user's natural language query."""
    q = query.lower()
    scores = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "overview"


def extract_entities(query: str, companies: list[str], roles: list[str]) -> dict[str, str | None]:
    """Extract company and role from query text."""
    q = query.lower()
    found_company = next((c for c in companies if c.lower() in q), None)
    found_role = next((r for r in roles if r.lower() in q), None)

    # Role aliases
    if not found_role:
        if any(x in q for x in ["de", "data eng", "pipeline", "etl"]):
            found_role = "Data Engineer"
        elif any(x in q for x in ["ds", "data sci", "ml ", "machine learning"]):
            found_role = "Data Scientist"
        elif any(x in q for x in ["da", "data anal", "analyst"]):
            found_role = "Data Analyst"

    return {"company": found_company, "role": found_role}


# ── KG queries — each returns KGResult with exact runnable Cypher ─────────────

def get_rounds_for_company_role(
    driver: Driver, company: str, role: str
) -> KGResult:
    cypher = """
MATCH (c:Company {name: $company})-[:HAS_ROUND]->(r:InterviewRound)
WHERE r.role = $role
RETURN r.name AS round, r.order AS order,
       r.duration_min AS duration, r.skills_tested AS skills
ORDER BY r.order"""
    params = {"company": company, "role": role}
    with driver.session() as session:
        data = [dict(r) for r in session.run(cypher, **params)]
    return KGResult(
        data=data,
        cypher=cypher,
        params=params,
        description=f"Interview rounds for {role} at {company}",
    )


def get_skills_for_company_role(
    driver: Driver, company: str, role: str
) -> KGResult:
    cypher = """
MATCH (c:Company {name: $company})-[n:NEEDS]->(s:Skill)
WHERE n.role = $role
RETURN s.name AS skill, n.importance AS importance
ORDER BY CASE n.importance
  WHEN 'Critical' THEN 1
  WHEN 'High'     THEN 2
  WHEN 'Medium'   THEN 3
  ELSE 4 END"""
    params = {"company": company, "role": role}
    with driver.session() as session:
        data = [dict(r) for r in session.run(cypher, **params)]
    return KGResult(
        data=data,
        cypher=cypher,
        params=params,
        description=f"Required skills for {role} at {company}",
    )


def get_sample_questions(
    driver: Driver, company: str, role: str, topic: str | None = None
) -> KGResult:
    if topic:
        cypher = """
MATCH (c:Company {name: $company})-[:HAS_ROUND]->(r:InterviewRound)
      -[:CONTAINS]->(q:InterviewQuestion)
WHERE r.role = $role AND q.topic = $topic
RETURN q.text AS question, q.difficulty AS difficulty,
       q.topic AS topic, q.source AS source, r.name AS round
ORDER BY q.difficulty
LIMIT 10"""
        params = {"company": company, "role": role, "topic": topic}
        desc = f"Sample {topic} questions for {role} at {company}"
    else:
        cypher = """
MATCH (c:Company {name: $company})-[:HAS_ROUND]->(r:InterviewRound)
      -[:CONTAINS]->(q:InterviewQuestion)
WHERE r.role = $role
RETURN q.text AS question, q.difficulty AS difficulty,
       q.topic AS topic, q.source AS source, r.name AS round
ORDER BY r.order, q.difficulty
LIMIT 10"""
        params = {"company": company, "role": role}
        desc = f"Sample questions for {role} at {company}"
    with driver.session() as session:
        data = [dict(r) for r in session.run(cypher, **params)]
    return KGResult(data=data, cypher=cypher, params=params, description=desc)


def get_resources_for_skill(
    driver: Driver, skill: str
) -> KGResult:
    cypher = """
MATCH (s:Skill {name: $skill})-[:HAS_RESOURCE]->(r:LearningResource)
RETURN r.name AS name, r.url AS url, r.type AS type"""
    params = {"skill": skill}
    with driver.session() as session:
        data = [dict(r) for r in session.run(cypher, **params)]
    return KGResult(
        data=data,
        cypher=cypher,
        params=params,
        description=f"Learning resources for {skill}",
    )


def compare_companies(
    driver: Driver, company1: str, company2: str, role: str
) -> tuple[KGResult, KGResult]:
    """Returns KGResults for both companies — compare Critical skills side by side."""
    cypher = """
MATCH (c:Company {name: $company})-[n:NEEDS]->(s:Skill)
WHERE n.role = $role AND n.importance = 'Critical'
RETURN s.name AS skill
ORDER BY s.name"""

    results = []
    for co in [company1, company2]:
        params = {"company": co, "role": role}
        with driver.session() as session:
            data = [dict(r) for r in session.run(cypher, **params)]
        results.append(KGResult(
            data=data,
            cypher=cypher,
            params=params,
            description=f"Critical skills for {role} at {co}",
        ))
    return results[0], results[1]


def get_company_overview(
    driver: Driver, company: str, role: str
) -> KGResult:
    cypher = """
MATCH (c:Company {name: $company})-[:HAS_ROUND]->(r:InterviewRound)
WHERE r.role = $role
OPTIONAL MATCH (c)-[n:NEEDS]->(s:Skill) WHERE n.role = $role
RETURN r.name AS round, r.order AS order, r.duration_min AS duration,
       r.skills_tested AS round_skills,
       collect(DISTINCT CASE WHEN n.importance = 'Critical' THEN s.name END) AS critical_skills
ORDER BY r.order"""
    params = {"company": company, "role": role}
    with driver.session() as session:
        data = [dict(r) for r in session.run(cypher, **params)]
    return KGResult(
        data=data,
        cypher=cypher,
        params=params,
        description=f"Full overview of {role} interview at {company}",
    )


def route_query(
    driver: Driver,
    query: str,
    companies: list[str],
    roles: list[str],
    default_company: str,
    default_role: str,
) -> list[KGResult]:
    """
    Route a natural language query to the right KG function(s).
    Returns a list of KGResults — may be multiple for comparisons.
    """
    intent   = detect_intent(query)
    entities = extract_entities(query, companies, roles)
    company  = entities["company"] or default_company
    role     = entities["role"]    or default_role

    # Comparison query — needs two companies
    if intent == "compare":
        found = [c for c in companies if c.lower() in query.lower()]
        if len(found) >= 2:
            r1, r2 = compare_companies(driver, found[0], found[1], role)
            return [r1, r2]

    # Extract topic for question queries
    topic = None
    topic_keywords = {
        "Kafka": ["kafka"], "Apache Spark": ["spark"],
        "SQL": ["sql"], "Python": ["python"],
        "System Design": ["system design"], "Data Modeling": ["data model"],
        "Machine Learning": ["machine learning", "ml"],
        "Statistics": ["statistics", "stats"],
        "A/B Testing": ["a/b", "ab test", "experiment"],
    }
    for topic_name, keywords in topic_keywords.items():
        if any(kw in query.lower() for kw in keywords):
            topic = topic_name
            break

    if intent == "rounds":
        return [get_rounds_for_company_role(driver, company, role)]
    elif intent == "skills":
        return [get_skills_for_company_role(driver, company, role)]
    elif intent == "questions":
        return [get_sample_questions(driver, company, role, topic)]
    elif intent == "resources":
        skill = topic or "SQL"
        return [get_resources_for_skill(driver, skill)]
    else:
        return [get_company_overview(driver, company, role)]