"""
Tests for KG Chat intent detection, entity extraction, and retrieval logic.
No Neo4j required for intent/entity tests.
"""

import pytest

from config import ROLES, COMPANIES
from kg.kg_chat import detect_intent, extract_entities
from data.resources import RESOURCES


# ── Intent Detection ─────────────────────────────────────────────────────────

class TestIntentDetection:

    @pytest.mark.parametrize("query,expected", [
        ("What rounds does Google have?", "rounds"),
        ("How many interview stages at Amazon?", "rounds"),
        ("What is the interview process at Meta?", "rounds"),
        ("What skills do I need for Data Scientist at Google?", "skills"),
        ("What tools should I know for Data Engineer?", "skills"),
        ("Show me sample questions for Amazon", "questions"),
        ("What questions are asked at Meta?", "questions"),
        ("Compare Google and Amazon for Data Scientist", "compare"),
        ("What is the difference between Meta and Apple?", "compare"),
        ("How should I study and prepare for SQL?", "resources"),
        ("What courses should I take to learn Python?", "resources"),
        ("Tell me about Google Data Scientist interviews", "overview"),
    ])
    def test_intent_detection(self, query, expected):
        assert detect_intent(query) == expected

    def test_unknown_query_defaults_to_overview(self):
        assert detect_intent("hello there") == "overview"

    def test_empty_query_defaults_to_overview(self):
        assert detect_intent("") == "overview"


# ── Entity Extraction ────────────────────────────────────────────────────────

class TestEntityExtraction:

    def test_extracts_company(self):
        result = extract_entities("Tell me about Google interviews", COMPANIES, ROLES)
        assert result["company"] == "Google"

    def test_extracts_role(self):
        result = extract_entities("Data Scientist at Amazon", COMPANIES, ROLES)
        assert result["role"] == "Data Scientist"
        assert result["company"] == "Amazon"

    def test_extracts_role_alias_ds(self):
        result = extract_entities("ds role at meta", COMPANIES, ROLES)
        assert result["role"] == "Data Scientist"

    def test_extracts_role_alias_de(self):
        result = extract_entities("data eng at google", COMPANIES, ROLES)
        assert result["role"] == "Data Engineer"

    def test_extracts_role_alias_da(self):
        result = extract_entities("data analyst at apple", COMPANIES, ROLES)
        assert result["role"] == "Data Analyst"

    def test_case_insensitive_company(self):
        result = extract_entities("what about amazon?", COMPANIES, ROLES)
        assert result["company"] == "Amazon"

    def test_no_entity_found(self):
        result = extract_entities("how do I prepare?", COMPANIES, ROLES)
        assert result["company"] is None
        assert result["role"] is None

    def test_multiple_companies_extracts_first(self):
        """When comparing, route_query handles this separately."""
        result = extract_entities("Compare Google and Amazon", COMPANIES, ROLES)
        # Should find at least one
        assert result["company"] in ("Google", "Amazon")


# ── Resources Validation ─────────────────────────────────────────────────────

class TestResources:

    def test_all_resources_have_required_fields(self):
        for i, r in enumerate(RESOURCES):
            assert "name" in r and r["name"], f"Resource {i} missing name"
            assert "url" in r and r["url"], f"Resource {i} '{r.get('name')}' missing url"
            assert "skill" in r and r["skill"], f"Resource {i} '{r.get('name')}' missing skill"
            assert "type" in r and r["type"], f"Resource {i} '{r.get('name')}' missing type"

    def test_resource_types_valid(self):
        valid = {"Course", "Book", "Tool", "Article"}
        for r in RESOURCES:
            assert r["type"] in valid, f"Resource '{r['name']}' has invalid type '{r['type']}'"

    def test_urls_look_valid(self):
        for r in RESOURCES:
            assert r["url"].startswith("http"), f"Resource '{r['name']}' URL doesn't start with http"

    def test_no_duplicate_resource_names(self):
        names = [r["name"] for r in RESOURCES]
        dupes = [n for n in names if names.count(n) > 1]
        # StatQuest appears twice (ML + Stats) — that's intentional
        # Just check no exact (name, skill) duplicate
        pairs = [(r["name"], r["skill"]) for r in RESOURCES]
        assert len(pairs) == len(set(pairs)), f"Duplicate (name, skill) pairs found"

    def test_covers_core_skills(self):
        skills_covered = {r["skill"] for r in RESOURCES}
        core = {"SQL", "Python", "Machine Learning", "Statistics", "Apache Spark"}
        missing = core - skills_covered
        assert missing == set(), f"No resources for core skills: {missing}"

    def test_minimum_resource_count(self):
        assert len(RESOURCES) >= 40, f"Only {len(RESOURCES)} resources, expected >= 40"