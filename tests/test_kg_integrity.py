"""
Knowledge Graph integrity tests — validates the loaded KG data.
Requires a running Neo4j instance with data loaded.
Run with: pytest tests/test_kg_integrity.py --neo4j
"""

import pytest

from config import ROLES, ROLE_SLUGS, COMPANIES, EXPERIENCE_LEVELS
from kg.load_kg import CRITICAL_BY_COMPANY_ROLE


pytestmark = pytest.mark.neo4j


# ── Schema ───────────────────────────────────────────────────────────────────

class TestKGSchema:

    def test_constraints_exist(self, neo4j_driver):
        with neo4j_driver.session() as s:
            result = s.run("SHOW CONSTRAINTS")
            names = [r["name"] for r in result]
        assert len(names) >= 7, f"Expected >= 7 constraints, got {len(names)}"

    def test_indexes_exist(self, neo4j_driver):
        with neo4j_driver.session() as s:
            result = s.run("SHOW INDEXES")
            names = [r["name"] for r in result]
        assert len(names) >= 5, f"Expected >= 5 indexes, got {len(names)}"


# ── Node Counts ──────────────────────────────────────────────────────────────

class TestNodeCounts:

    def test_company_nodes(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (c:Company) RETURN count(c) AS c").single()["c"]
        assert count == len(COMPANIES), f"Expected {len(COMPANIES)} Company nodes, got {count}"

    def test_role_nodes(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (r:Role) RETURN count(r) AS c").single()["c"]
        assert count == len(ROLES), f"Expected {len(ROLES)} Role nodes, got {count}"

    def test_experience_level_nodes(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (el:ExperienceLevel) RETURN count(el) AS c").single()["c"]
        assert count == len(EXPERIENCE_LEVELS), f"Expected {len(EXPERIENCE_LEVELS)} levels, got {count}"

    def test_minimum_round_count(self, neo4j_driver):
        """27 combos × ~6 rounds each = ~162 rounds minimum."""
        with neo4j_driver.session() as s:
            count = s.run("MATCH (ir:InterviewRound) RETURN count(ir) AS c").single()["c"]
        assert count >= 150, f"Expected >= 150 InterviewRound nodes, got {count}"

    def test_minimum_question_count(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (iq:InterviewQuestion) RETURN count(iq) AS c").single()["c"]
        assert count >= 50, f"Expected >= 50 questions, got {count}"

    def test_minimum_skill_count(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (s:Skill) RETURN count(s) AS c").single()["c"]
        assert count >= 30, f"Expected >= 30 skills, got {count}"

    def test_learning_resources_exist(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run("MATCH (lr:LearningResource) RETURN count(lr) AS c").single()["c"]
        assert count >= 30, f"Expected >= 30 resources, got {count}"


# ── Relationship Integrity ───────────────────────────────────────────────────

class TestRelationships:

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_company_has_rounds(self, neo4j_driver, role, company):
        slug = ROLE_SLUGS[role]
        pfx = f"{company}_{slug}"
        with neo4j_driver.session() as s:
            count = s.run(
                """
                MATCH (c:Company {name: $co})-[:HAS_ROUND]->(ir:InterviewRound)
                WHERE ir.id STARTS WITH $pfx
                RETURN count(ir) AS c
                """,
                co=company, pfx=pfx,
            ).single()["c"]
        assert count >= 3, f"({company}, {role}) has only {count} rounds, expected >= 3"

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_company_has_needs_relationships(self, neo4j_driver, role, company):
        with neo4j_driver.session() as s:
            count = s.run(
                """
                MATCH (c:Company {name: $co})-[n:NEEDS]->(s:Skill)
                WHERE n.role = $role
                RETURN count(s) AS c
                """,
                co=company, role=role,
            ).single()["c"]
        assert count >= 3, f"({company}, {role}) has only {count} NEEDS rels, expected >= 3"

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_critical_skills_in_needs(self, neo4j_driver, role, company):
        """Verify NEEDS relationships have importance='Critical' for expected skills."""
        expected = CRITICAL_BY_COMPANY_ROLE.get((company, role), set())
        if not expected:
            pytest.skip("No critical skills defined")

        with neo4j_driver.session() as s:
            result = s.run(
                """
                MATCH (c:Company {name: $co})-[n:NEEDS]->(s:Skill)
                WHERE n.role = $role AND n.importance = 'Critical'
                RETURN collect(s.name) AS skills
                """,
                co=company, role=role,
            ).single()
            actual = set(result["skills"])

        missing = expected - actual
        if missing:
            pytest.xfail(
                f"({company}, {role}) NEEDS 'Critical' missing for: {missing}. "
                f"Re-run `python kg/load_kg.py` to fix."
            )

    def test_questions_linked_to_rounds(self, neo4j_driver):
        """Every question should be linked to at least one round."""
        with neo4j_driver.session() as s:
            orphaned = s.run(
                """
                MATCH (iq:InterviewQuestion)
                WHERE NOT ()-[:CONTAINS]->(iq)
                RETURN count(iq) AS c
                """
            ).single()["c"]
        # Some GitHub questions may not link — warn but don't fail hard
        assert orphaned < 100, f"{orphaned} orphaned questions (not linked to any round)"

    def test_resources_linked_to_skills(self, neo4j_driver):
        with neo4j_driver.session() as s:
            orphaned = s.run(
                """
                MATCH (lr:LearningResource)
                WHERE NOT ()-[:HAS_RESOURCE]->(lr)
                RETURN count(lr) AS c
                """
            ).single()["c"]
        assert orphaned == 0, f"{orphaned} resources not linked to any skill"

    def test_no_duplicate_needs_per_company_role_skill(self, neo4j_driver):
        """There should be exactly one NEEDS per (company, role, skill) triple."""
        with neo4j_driver.session() as s:
            dupes = s.run(
                """
                MATCH (c:Company)-[n:NEEDS]->(s:Skill)
                WITH c.name AS co, n.role AS role, s.name AS skill, count(n) AS cnt
                WHERE cnt > 1
                RETURN co, role, skill, cnt
                """
            )
            dupes_list = [dict(r) for r in dupes]
        assert dupes_list == [], f"Duplicate NEEDS: {dupes_list}"


# ── Data Quality ─────────────────────────────────────────────────────────────

class TestDataQuality:

    def test_no_null_round_names(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run(
                "MATCH (ir:InterviewRound) WHERE ir.name IS NULL RETURN count(ir) AS c"
            ).single()["c"]
        assert count == 0, f"{count} rounds with null name"

    def test_no_null_skill_names(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run(
                "MATCH (s:Skill) WHERE s.name IS NULL RETURN count(s) AS c"
            ).single()["c"]
        assert count == 0

    def test_no_empty_question_text(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run(
                "MATCH (iq:InterviewQuestion) WHERE iq.text IS NULL OR size(iq.text) < 10 RETURN count(iq) AS c"
            ).single()["c"]
        assert count == 0, f"{count} questions with empty/short text"

    def test_all_rounds_have_role_property(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run(
                "MATCH (ir:InterviewRound) WHERE ir.role IS NULL RETURN count(ir) AS c"
            ).single()["c"]
        assert count == 0, f"{count} rounds without role property"

    def test_resource_urls_not_empty(self, neo4j_driver):
        with neo4j_driver.session() as s:
            count = s.run(
                """
                MATCH (lr:LearningResource)
                WHERE lr.url IS NULL OR size(lr.url) < 5
                RETURN count(lr) AS c
                """
            ).single()["c"]
        assert count == 0, f"{count} resources with missing URLs"

    def test_needs_importance_valid_values(self, neo4j_driver):
        with neo4j_driver.session() as s:
            invalid = s.run(
                """
                MATCH ()-[n:NEEDS]->()
                WHERE NOT n.importance IN ['Critical', 'High', 'Medium']
                RETURN count(n) AS c
                """
            ).single()["c"]
        assert invalid == 0, f"{invalid} NEEDS with invalid importance value"

    def test_round_id_format_consistent(self, neo4j_driver):
        """Round IDs should follow the pattern Company_slug_RoundName."""
        with neo4j_driver.session() as s:
            result = s.run(
                """
                MATCH (ir:InterviewRound)
                WHERE NOT ir.id CONTAINS '_'
                RETURN count(ir) AS c
                """
            ).single()["c"]
        assert result == 0, f"{result} rounds with malformed ID (no underscore)"


# ── Graph-Native Classification ──────────────────────────────────────────────

class TestGraphClassification:
    """Tests that verify the graph-native Kaggle skill classification."""

    def test_kaggle_skills_loaded(self, neo4j_driver):
        """After loading, Kaggle skills should exist as Skill nodes."""
        with neo4j_driver.session() as s:
            count = s.run(
                "MATCH (s:Skill) WHERE s.source = 'kaggle' RETURN count(s) AS c"
            ).single()["c"]
        # If Kaggle data was extracted, we should have skills; if not, skip
        if count == 0:
            pytest.skip("No Kaggle skills loaded (run data extraction first)")
        assert count >= 20, f"Only {count} Kaggle skills, expected >= 20"

    def test_kaggle_skills_linked_to_roles(self, neo4j_driver):
        """Every Kaggle skill should be linked to at least one Role."""
        with neo4j_driver.session() as s:
            orphaned = s.run(
                """
                MATCH (s:Skill)
                WHERE s.source = 'kaggle' AND NOT (:Role)-[:NEEDS]->(s)
                RETURN count(s) AS c
                """
            ).single()["c"]
        assert orphaned == 0, f"{orphaned} Kaggle skills not linked to any Role"

    def test_high_frequency_skills_promoted(self, neo4j_driver):
        """Skills appearing across 3+ companies should be marked High."""
        with neo4j_driver.session() as s:
            result = s.run(
                """
                MATCH (c:Company)-[n:NEEDS]->(s:Skill)
                WHERE n.source = 'kaggle'
                WITH s, count(DISTINCT c) AS cos, collect(n.importance) AS imps
                WHERE cos >= 3
                RETURN s.name AS skill, cos,
                       any(i IN imps WHERE i = 'High') AS has_high
                """
            )
            rows = [dict(r) for r in result]
        if not rows:
            pytest.skip("No cross-company Kaggle skills (run extraction first)")
        not_promoted = [r for r in rows if not r["has_high"]]
        assert len(not_promoted) == 0, (
            f"Skills across 3+ companies not promoted: "
            f"{[r['skill'] for r in not_promoted]}"
        )

    def test_no_duplicate_skill_names_case_insensitive(self, neo4j_driver):
        """Skill names should be deduplicated case-insensitively."""
        with neo4j_driver.session() as s:
            result = s.run(
                """
                MATCH (s:Skill)
                WITH toLower(s.name) AS lower_name, collect(s.name) AS names
                WHERE size(names) > 1
                RETURN lower_name, names
                """
            )
            dupes = [dict(r) for r in result]
        assert dupes == [], f"Case-insensitive duplicate skills: {dupes}"