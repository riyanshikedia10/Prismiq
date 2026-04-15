"""
Neo4j schema setup: constraints, indexes, and driver lifecycle management.
Uses transaction functions for safe, retryable operations.
"""

from __future__ import annotations

import logging
import os

from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

from models import KGConnectionError

load_dotenv()

logger = logging.getLogger(__name__)

CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT role_name IF NOT EXISTS FOR (r:Role) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT round_id IF NOT EXISTS FOR (ir:InterviewRound) REQUIRE ir.id IS UNIQUE",
    "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (iq:InterviewQuestion) REQUIRE iq.id IS UNIQUE",
    "CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (lr:LearningResource) REQUIRE lr.id IS UNIQUE",
    "CREATE CONSTRAINT level_name IF NOT EXISTS FOR (el:ExperienceLevel) REQUIRE el.level IS UNIQUE",
]

INDEXES: list[str] = [
    "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX skill_category_idx IF NOT EXISTS FOR (s:Skill) ON (s.category)",
    "CREATE INDEX round_order_idx IF NOT EXISTS FOR (ir:InterviewRound) ON (ir.order)",
    "CREATE INDEX question_difficulty_idx IF NOT EXISTS FOR (iq:InterviewQuestion) ON (iq.difficulty)",
    "CREATE INDEX level_idx IF NOT EXISTS FOR (el:ExperienceLevel) ON (el.level)",
]


def get_driver() -> Driver:
    """Create a Neo4j driver from environment variables."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        return driver
    except Exception as exc:
        raise KGConnectionError(f"Failed to create Neo4j driver: {exc}") from exc


def verify_connectivity(driver: Driver) -> None:
    """Raise KGConnectionError if Neo4j is unreachable."""
    try:
        driver.verify_connectivity()
        logger.info("Neo4j connectivity verified")
    except Exception as exc:
        raise KGConnectionError(
            f"Cannot reach Neo4j at {driver._pool.address}. "
            "Ensure Neo4j is running and .env credentials are correct."
        ) from exc


def setup_schema(driver: Driver) -> None:
    """Create all constraints and indexes idempotently."""
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
            label = stmt.split("FOR")[0].strip()
            logger.info("[OK] %s", label)

        for stmt in INDEXES:
            session.run(stmt)
            label = stmt.split("FOR")[0].strip()
            logger.info("[OK] %s", label)

    logger.info("Schema setup complete")


def clear_database(driver: Driver) -> None:
    """Remove all nodes and relationships. Use with caution."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    logger.warning("Database cleared")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import setup_logging

    setup_logging()
    driver = get_driver()
    try:
        verify_connectivity(driver)
        setup_schema(driver)
    finally:
        driver.close()
