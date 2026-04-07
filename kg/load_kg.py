"""
Load processed JSON data into Neo4j Knowledge Graph for Data Analyst role.
Reads data/processed/da_leetcode_{company}.json + da_job_skills_{company}.json
(Approach B) and data/processed/{company}_data.json (Approach A)
for each company and creates nodes + relationships using MERGE to avoid duplicates.
"""

import json
import os
import glob

from kg.schema import get_driver, setup_schema

COMPANIES = ["Google", "Amazon", "Meta", "Apple", "Netflix"]
EXPERIENCE_LEVELS = ["Entry", "Mid", "Senior"]
ROLE = "Data Analyst"


def _run(session, query, **params):
    session.run(query, **params)


def load_experience_levels(session):
    for level in EXPERIENCE_LEVELS:
        session.run(
            "MERGE (el:ExperienceLevel {level: $level})",
            level=level,
        )
    print(f"  [Levels] {len(EXPERIENCE_LEVELS)} experience levels")


def load_role(session):
    session.run("MERGE (r:Role {name: $name})", name=ROLE)
    print(f"  [Role] {ROLE}")


def load_company(session, company_name: str, data: dict):
    """Load all data for a single company into Neo4j."""

    # Company node
    session.run("MERGE (c:Company {name: $name})", name=company_name)

    # Role → Skills (NEEDS)
    for skill in data.get("skills", []):
        session.run(
            """
            MERGE (s:Skill {name: $name})
            ON CREATE SET s.category = $category
            """,
            name=skill["name"],
            category=skill.get("category", "Technical"),
        )
        # Company REQUIRES Skill
        session.run(
            """
            MATCH (c:Company {name: $company})
            MATCH (s:Skill {name: $skill})
            MERGE (c)-[r:REQUIRES]->(s)
            SET r.importance = $importance
            """,
            company=company_name,
            skill=skill["name"],
            importance=skill.get("importance", "Medium"),
        )
        # Role NEEDS Skill
        session.run(
            """
            MATCH (r:Role {name: $role})
            MATCH (s:Skill {name: $skill})
            MERGE (r)-[:NEEDS]->(s)
            """,
            role=ROLE,
            skill=skill["name"],
        )

    n_skills = len(data.get("skills", []))
    print(f"  [Skills] {n_skills} skills + REQUIRES/NEEDS edges")

    # Interview Rounds
    for round_info in data.get("rounds", []):
        round_id = f"{company_name}_{round_info['name']}".replace(" ", "_")
        session.run(
            """
            MERGE (ir:InterviewRound {id: $id})
            ON CREATE SET ir.name = $name,
                          ir.order = $order,
                          ir.duration_min = $duration,
                          ir.question_types = $qtypes
            """,
            id=round_id,
            name=round_info["name"],
            order=round_info["order"],
            duration=round_info.get("duration_min", 45),
            qtypes=round_info.get("question_types", []),
        )
        session.run(
            """
            MATCH (c:Company {name: $company})
            MATCH (ir:InterviewRound {id: $round_id})
            MERGE (c)-[r:HAS_ROUND]->(ir)
            SET r.order = $order
            """,
            company=company_name,
            round_id=round_id,
            order=round_info["order"],
        )

    n_rounds = len(data.get("rounds", []))
    print(f"  [Rounds] {n_rounds} rounds + HAS_ROUND edges")

    # Interview Questions
    q_count = 0
    for i, q in enumerate(data.get("sample_questions", [])):
        q_id = f"{company_name}_DA_Q{i+1}"
        round_name = q.get("round", "")
        round_id = f"{company_name}_{round_name}".replace(" ", "_")

        session.run(
            """
            MERGE (iq:InterviewQuestion {id: $id})
            ON CREATE SET iq.text = $text,
                          iq.difficulty = $difficulty,
                          iq.round_name = $round_name
            """,
            id=q_id,
            text=q["text"],
            difficulty=q.get("difficulty", "Medium"),
            round_name=round_name,
        )

        # Round CONTAINS Question
        session.run(
            """
            MATCH (ir:InterviewRound {id: $round_id})
            MATCH (iq:InterviewQuestion {id: $q_id})
            MERGE (ir)-[:CONTAINS]->(iq)
            """,
            round_id=round_id,
            q_id=q_id,
        )

        # Question TESTS Skill
        for skill_name in q.get("skills_tested", []):
            session.run(
                """
                MERGE (s:Skill {name: $skill})
                """,
                skill=skill_name,
            )
            session.run(
                """
                MATCH (iq:InterviewQuestion {id: $q_id})
                MATCH (s:Skill {name: $skill})
                MERGE (iq)-[:TESTS]->(s)
                """,
                q_id=q_id,
                skill=skill_name,
            )

        # Question FOR_LEVEL ExperienceLevel
        levels = q.get("experience_levels", EXPERIENCE_LEVELS)
        for level in levels:
            session.run(
                """
                MATCH (iq:InterviewQuestion {id: $q_id})
                MATCH (el:ExperienceLevel {level: $level})
                MERGE (iq)-[:FOR_LEVEL]->(el)
                """,
                q_id=q_id,
                level=level,
            )

        q_count += 1

    print(f"  [Questions] {q_count} questions + CONTAINS/TESTS/FOR_LEVEL edges")

    # Learning Resources
    r_count = 0
    for i, res in enumerate(data.get("learning_resources", [])):
        res_id = f"{company_name}_DA_R{i+1}"
        session.run(
            """
            MERGE (lr:LearningResource {id: $id})
            ON CREATE SET lr.name = $name,
                          lr.url = $url,
                          lr.type = $type
            """,
            id=res_id,
            name=res["name"],
            url=res.get("url", ""),
            type=res.get("type", "Article"),
        )
        skill_name = res.get("skill", "")
        if skill_name:
            session.run(
                """
                MERGE (s:Skill {name: $skill})
                """,
                skill=skill_name,
            )
            session.run(
                """
                MATCH (s:Skill {name: $skill})
                MATCH (lr:LearningResource {id: $res_id})
                MERGE (s)-[:HAS_RESOURCE]->(lr)
                """,
                skill=skill_name,
                res_id=res_id,
            )
        r_count += 1

    print(f"  [Resources] {r_count} resources + HAS_RESOURCE edges")


def load_leetcode_questions(session, company_name: str, data: dict):
    """Load LeetCode problems (Approach B, Source 1) into Neo4j."""
    questions = data.get("questions", [])
    if not questions:
        return 0

    q_count = 0
    for q in questions:
        q_id = q.get("id", f"{company_name}_DA_LC{q_count+1}")
        round_name = q.get("round", "Technical Screen")
        round_id = f"{company_name}_{round_name}".replace(" ", "_")

        session.run(
            """
            MERGE (iq:InterviewQuestion {id: $id})
            ON CREATE SET iq.text = $text,
                          iq.difficulty = $difficulty,
                          iq.round_name = $round_name,
                          iq.source = $source,
                          iq.source_url = $source_url,
                          iq.acceptance = $acceptance
            """,
            id=q_id,
            text=q["text"],
            difficulty=q.get("difficulty", "Medium"),
            round_name=round_name,
            source="leetcode",
            source_url=q.get("source_url", ""),
            acceptance=q.get("acceptance", ""),
        )

        session.run(
            """
            MATCH (ir:InterviewRound {id: $round_id})
            MATCH (iq:InterviewQuestion {id: $q_id})
            MERGE (ir)-[:CONTAINS]->(iq)
            """,
            round_id=round_id,
            q_id=q_id,
        )

        for skill_name in q.get("skills_tested", []):
            session.run("MERGE (s:Skill {name: $skill})", skill=skill_name)
            session.run(
                """
                MATCH (iq:InterviewQuestion {id: $q_id})
                MATCH (s:Skill {name: $skill})
                MERGE (iq)-[:TESTS]->(s)
                """,
                q_id=q_id,
                skill=skill_name,
            )

        for level in q.get("experience_levels", EXPERIENCE_LEVELS):
            session.run(
                """
                MATCH (iq:InterviewQuestion {id: $q_id})
                MATCH (el:ExperienceLevel {level: $level})
                MERGE (iq)-[:FOR_LEVEL]->(el)
                """,
                q_id=q_id,
                level=level,
            )
        q_count += 1

    return q_count


def load_job_skills(session, company_name: str, data: dict):
    """Load verified DA job-posting skills (Approach B, Source 2) into Neo4j."""
    skills = data.get("skills", [])
    if not skills:
        return 0

    s_count = 0
    for skill in skills:
        session.run(
            """
            MERGE (s:Skill {name: $name})
            ON CREATE SET s.category = $category
            """,
            name=skill["name"],
            category=skill.get("category", "Technical"),
        )
        session.run(
            """
            MATCH (c:Company {name: $company})
            MATCH (s:Skill {name: $skill})
            MERGE (c)-[r:REQUIRES]->(s)
            ON CREATE SET r.importance = $importance, r.source = 'kaggle'
            """,
            company=company_name,
            skill=skill["name"],
            importance=skill.get("importance", "Medium"),
        )
        session.run(
            """
            MATCH (r:Role {name: $role})
            MATCH (s:Skill {name: $skill})
            MERGE (r)-[:NEEDS]->(s)
            """,
            role=ROLE,
            skill=skill["name"],
        )
        s_count += 1

    return s_count


def load_kaggle_data(session, company_name: str):
    """Load Approach B data (LeetCode + Kaggle DA job skills) for a company."""
    lc_path = f"data/processed/da_leetcode_{company_name.lower()}.json"
    js_path = f"data/processed/da_job_skills_{company_name.lower()}.json"

    lc_count = 0
    js_count = 0

    if os.path.exists(lc_path):
        with open(lc_path, "r") as f:
            lc_data = json.load(f)
        lc_count = load_leetcode_questions(session, company_name, lc_data)

    if os.path.exists(js_path):
        with open(js_path, "r") as f:
            js_data = json.load(f)
        js_count = load_job_skills(session, company_name, js_data)

    if lc_count or js_count:
        print(f"  [Approach B] {lc_count} LeetCode problems, {js_count} DA-verified skills")
    else:
        print(f"  [Approach B] No Approach B data found for {company_name}")


def load_all(driver):
    """Load all company data from data/processed/ into Neo4j for Data Analyst."""
    with driver.session() as session:
        load_experience_levels(session)
        load_role(session)

        for company in COMPANIES:
            filepath = f"data/processed/{company.lower()}_data.json"
            if not os.path.exists(filepath):
                print(f"\n[{company}] SKIPPED Approach A — {filepath} not found")
            else:
                print(f"\n[{company}] Loading Approach A (GPT)...")
                with open(filepath, "r") as f:
                    data = json.load(f)
                load_company(session, company, data)

            print(f"\n[{company}] Loading Approach B (Kaggle/LeetCode)...")
            load_kaggle_data(session, company)

    # Print summary
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS nodes")
        nodes = result.single()["nodes"]
        result = session.run("MATCH ()-[r]->() RETURN count(r) AS rels")
        rels = result.single()["rels"]
        print(f"\n{'='*40}")
        print(f"Total nodes: {nodes}")
        print(f"Total relationships: {rels}")
        print(f"{'='*40}")


if __name__ == "__main__":
    driver = get_driver()
    try:
        print("Setting up schema...")
        setup_schema(driver)
        print()
        print(f"Loading Knowledge Graph for role: {ROLE}")
        print()
        load_all(driver)
    finally:
        driver.close()
