"""
Neo4j schema setup: constraints, indexes, and driver utility.
Run this once to initialize the database schema before loading data.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

CONSTRAINTS = [
    "CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT role_name IF NOT EXISTS FOR (r:Role) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT round_id IF NOT EXISTS FOR (ir:InterviewRound) REQUIRE ir.id IS UNIQUE",
    "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (iq:InterviewQuestion) REQUIRE iq.id IS UNIQUE",
    "CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (lr:LearningResource) REQUIRE lr.id IS UNIQUE",
    "CREATE CONSTRAINT level_name IF NOT EXISTS FOR (el:ExperienceLevel) REQUIRE el.level IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX skill_category_idx IF NOT EXISTS FOR (s:Skill) ON (s.category)",
    "CREATE INDEX round_order_idx IF NOT EXISTS FOR (ir:InterviewRound) ON (ir.order)",
    "CREATE INDEX question_difficulty_idx IF NOT EXISTS FOR (iq:InterviewQuestion) ON (iq.difficulty)",
    "CREATE INDEX level_idx IF NOT EXISTS FOR (el:ExperienceLevel) ON (el.level)",
]


def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def setup_schema(driver):
    """Create all constraints and indexes in Neo4j."""
    with driver.session() as session:
        for constraint in CONSTRAINTS:
            session.run(constraint)
            print(f"  [OK] {constraint.split('FOR')[0].strip()}")

        for index in INDEXES:
            session.run(index)
            print(f"  [OK] {index.split('FOR')[0].strip()}")

    print("\nSchema setup complete.")


def clear_database(driver):
    """Remove all nodes and relationships. Use with caution."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Database cleared.")


if __name__ == "__main__":
    driver = get_driver()
    try:
        print("Setting up Neo4j schema...\n")
        setup_schema(driver)
    finally:
        driver.close()
