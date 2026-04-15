"""
Tests for config.py and models.py — validates constants, settings, and Pydantic schemas.
No Neo4j required.
"""

import os
import pytest

from config import (
    ROLES, ROLE_SLUGS, COMPANIES, EXPERIENCE_LEVELS,
    COMPANY_ALIASES, JOB_TITLE_KEYWORDS, LEETCODE_CSV_MAP,
    COMPANY_COLORS, LEETCODE_DIFFICULTY_FILTER,
)
from models import (
    Skill, InterviewRound, InterviewQuestion, LearningResource,
    CompanyData, GeneratedQuestion, EvaluationResult,
    Importance, Difficulty, ExperienceLevel,
)


# ── Config Constants ─────────────────────────────────────────────────────────

class TestConfigConstants:

    def test_all_roles_have_slugs(self):
        for role in ROLES:
            assert role in ROLE_SLUGS, f"Role '{role}' missing from ROLE_SLUGS"

    def test_slugs_are_unique(self):
        slugs = list(ROLE_SLUGS.values())
        assert len(slugs) == len(set(slugs)), "Duplicate slugs found"

    def test_all_companies_have_aliases(self):
        for company in COMPANIES:
            assert company in COMPANY_ALIASES, f"Company '{company}' missing from COMPANY_ALIASES"

    def test_all_companies_have_colors(self):
        for company in COMPANIES:
            assert company in COMPANY_COLORS, f"Company '{company}' missing from COMPANY_COLORS"

    def test_all_companies_have_leetcode_map_entry(self):
        for company in COMPANIES:
            assert company in LEETCODE_CSV_MAP, f"Company '{company}' missing from LEETCODE_CSV_MAP"

    def test_all_roles_have_title_keywords(self):
        for role in ROLES:
            assert role in JOB_TITLE_KEYWORDS, f"Role '{role}' missing from JOB_TITLE_KEYWORDS"
            assert len(JOB_TITLE_KEYWORDS[role]) > 0, f"Role '{role}' has empty keyword list"

    def test_all_roles_have_difficulty_filter(self):
        for role in ROLES:
            assert role in LEETCODE_DIFFICULTY_FILTER, f"Role '{role}' missing from LEETCODE_DIFFICULTY_FILTER"

    def test_experience_levels_ordered(self):
        assert EXPERIENCE_LEVELS == ["Entry", "Mid", "Senior"]

    def test_aliases_are_lowercase(self):
        for company, aliases in COMPANY_ALIASES.items():
            for alias in aliases:
                assert alias == alias.lower(), f"Alias '{alias}' for {company} is not lowercase"

    def test_company_count_is_nine(self):
        assert len(COMPANIES) == 9, f"Expected 9 companies, got {len(COMPANIES)}"


# ── Settings ─────────────────────────────────────────────────────────────────

class TestSettings:

    def test_settings_from_env_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from config import Settings
        from models import ConfigError
        with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
            Settings.from_env()

    def test_settings_from_env_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        from config import Settings
        s = Settings.from_env()
        assert s.openai_api_key == "test-key-123"
        assert s.neo4j_uri == os.getenv("NEO4J_URI", "bolt://localhost:7687")


# ── Pydantic Models ──────────────────────────────────────────────────────────

class TestModels:

    def test_skill_strips_name(self):
        s = Skill(name="  Python  ")
        assert s.name == "Python"

    def test_skill_rejects_empty_name(self):
        with pytest.raises(Exception):
            Skill(name="")

    def test_skill_rejects_long_name(self):
        with pytest.raises(Exception):
            Skill(name="x" * 201)

    def test_interview_round_validates_order(self):
        with pytest.raises(Exception):
            InterviewRound(name="Test", order=0)

    def test_interview_round_validates_duration(self):
        with pytest.raises(Exception):
            InterviewRound(name="Test", order=1, duration_min=5)

    def test_interview_question_rejects_short_text(self):
        with pytest.raises(Exception):
            InterviewQuestion(text="Hi")

    def test_interview_question_defaults(self):
        q = InterviewQuestion(text="What is the difference between L1 and L2 regularization?")
        assert q.difficulty == "Medium"
        assert q.experience_levels == ["Entry", "Mid", "Senior"]

    def test_generated_question_validates(self):
        gq = GeneratedQuestion(
            question="Design a star schema for an e-commerce platform.",
            skills_tested=["Data Modeling", "SQL"],
            difficulty="Medium",
            round="Onsite: Data Modeling",
        )
        assert len(gq.question) > 5

    def test_evaluation_result_score_bounds(self):
        with pytest.raises(Exception):
            EvaluationResult(score=0)
        with pytest.raises(Exception):
            EvaluationResult(score=11)
        er = EvaluationResult(score=7)
        assert er.score == 7

    def test_company_data_defaults(self):
        cd = CompanyData()
        assert cd.rounds == []
        assert cd.skills == []

    def test_enums_have_expected_values(self):
        assert Importance.CRITICAL.value == "Critical"
        assert Difficulty.HARD.value == "Hard"
        assert ExperienceLevel.ENTRY.value == "Entry"
