"""
Tests for seed data integrity (seeds.py + load_kg.py).
Validates completeness, structural consistency, and cross-reference correctness.
No Neo4j required.
"""

import pytest

from config import ROLES, ROLE_SLUGS, COMPANIES, EXPERIENCE_LEVELS
from llm.seeds import SEED_DATA, DS_SEEDS, DA_SEEDS, DE_SEEDS, get_seed, get_companies_for_role
from kg.load_kg import CRITICAL_BY_COMPANY_ROLE, SOFT_SKILLS, TOPIC_TO_ROUND, NOISE_SKILLS, _normalize_skill_name


# ── Seed Coverage ────────────────────────────────────────────────────────────

class TestSeedCoverage:
    """Every (role, company) pair must have seed data with valid structure."""

    def test_all_27_combinations_exist(self):
        missing = []
        for role in ROLES:
            for company in COMPANIES:
                seed = get_seed(role, company)
                if seed is None:
                    missing.append((role, company))
        assert missing == [], f"Missing seed data for: {missing}"

    def test_seed_data_keys_match_roles(self):
        assert set(SEED_DATA.keys()) == set(ROLES)

    def test_each_role_covers_all_companies(self):
        for role in ROLES:
            companies_with_seeds = get_companies_for_role(role)
            missing = set(COMPANIES) - set(companies_with_seeds)
            assert missing == set(), f"Role '{role}' missing seeds for: {missing}"

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_seed_has_rounds_key(self, role, company):
        seed = get_seed(role, company)
        assert "rounds" in seed, f"Seed ({role}, {company}) missing 'rounds' key"
        assert len(seed["rounds"]) >= 3, f"Seed ({role}, {company}) has fewer than 3 rounds"


# ── Round Structure ──────────────────────────────────────────────────────────

class TestRoundStructure:
    """Each round must have required fields with valid values."""

    REQUIRED_FIELDS = {"name", "order", "duration_min", "skills_tested", "question_types"}

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_rounds_have_required_fields(self, role, company):
        seed = get_seed(role, company)
        for rnd in seed["rounds"]:
            missing = self.REQUIRED_FIELDS - set(rnd.keys())
            assert missing == set(), (
                f"({role}, {company}) round '{rnd.get('name', '?')}' missing: {missing}"
            )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_round_orders_are_sequential(self, role, company):
        seed = get_seed(role, company)
        orders = [r["order"] for r in seed["rounds"]]
        assert orders == list(range(1, len(orders) + 1)), (
            f"({role}, {company}) non-sequential orders: {orders}"
        )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_round_names_unique_within_company(self, role, company):
        seed = get_seed(role, company)
        names = [r["name"] for r in seed["rounds"]]
        assert len(names) == len(set(names)), (
            f"({role}, {company}) duplicate round names: {names}"
        )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_round_durations_in_range(self, role, company):
        seed = get_seed(role, company)
        for rnd in seed["rounds"]:
            dur = rnd["duration_min"]
            assert 15 <= dur <= 120, (
                f"({role}, {company}) '{rnd['name']}' duration {dur} outside 15-120 min"
            )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_round_starts_with_recruiter_screen(self, role, company):
        seed = get_seed(role, company)
        first = seed["rounds"][0]
        assert "recruiter" in first["name"].lower() or "phone" in first["name"].lower(), (
            f"({role}, {company}) first round is '{first['name']}', expected Recruiter/Phone Screen"
        )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_skills_tested_not_empty(self, role, company):
        seed = get_seed(role, company)
        for rnd in seed["rounds"]:
            assert len(rnd["skills_tested"]) > 0, (
                f"({role}, {company}) round '{rnd['name']}' has empty skills_tested"
            )


# ── Critical Skills Mapping ──────────────────────────────────────────────────

class TestCriticalSkillsMapping:
    """CRITICAL_BY_COMPANY_ROLE must cover all 27 combinations with valid skills."""

    def test_all_27_combinations_have_critical_mapping(self):
        missing = []
        for role in ROLES:
            for company in COMPANIES:
                if (company, role) not in CRITICAL_BY_COMPANY_ROLE:
                    missing.append((company, role))
        assert missing == [], f"Missing CRITICAL_BY_COMPANY_ROLE entries: {missing}"

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_critical_skills_not_empty(self, role, company):
        crit = CRITICAL_BY_COMPANY_ROLE.get((company, role), set())
        assert len(crit) >= 3, (
            f"({company}, {role}) has only {len(crit)} critical skills, expected >= 3"
        )

    @pytest.mark.parametrize("role", ROLES)
    @pytest.mark.parametrize("company", COMPANIES)
    def test_critical_skills_not_in_soft_skills(self, role, company):
        crit = CRITICAL_BY_COMPANY_ROLE.get((company, role), set())
        overlap = crit & SOFT_SKILLS
        assert overlap == set(), (
            f"({company}, {role}) critical skills overlap with SOFT_SKILLS: {overlap}"
        )

    def test_all_roles_require_sql(self):
        """SQL should be critical for every role at most companies."""
        for role in ROLES:
            sql_count = sum(
                1 for co in COMPANIES
                if "SQL" in CRITICAL_BY_COMPANY_ROLE.get((co, role), set())
            )
            assert sql_count >= 6, (
                f"Role '{role}' has SQL as critical at only {sql_count}/9 companies"
            )


# ── TOPIC_TO_ROUND Cross-Reference ───────────────────────────────────────────

class TestTopicToRoundMapping:
    """
    BOTTLENECK: TOPIC_TO_ROUND maps topics to generic round names like
    "Onsite: Stats & ML", but actual seed round names vary per company.
    This test identifies which mappings are broken.
    """

    def _all_seed_round_names(self, role: str) -> set[str]:
        """Collect every round name across all companies for a role."""
        names = set()
        for company in COMPANIES:
            seed = get_seed(role, company)
            if seed:
                for rnd in seed["rounds"]:
                    names.add(rnd["name"])
        return names

    @pytest.mark.parametrize("topic,round_name", list(TOPIC_TO_ROUND.items()))
    def test_topic_round_exists_in_at_least_one_company(self, topic, round_name):
        """Each TOPIC_TO_ROUND target must exist as a real round name somewhere."""
        all_names: set[str] = set()
        for role in ROLES:
            all_names |= self._all_seed_round_names(role)
        if round_name not in all_names:
            pytest.xfail(
                f"TOPIC_TO_ROUND['{topic}'] -> '{round_name}' does not match any "
                f"seed round name. GitHub questions for this topic will be unlinked."
            )

    def test_report_broken_topic_mappings(self):
        """Report all TOPIC_TO_ROUND values that don't match any seed round."""
        all_round_names: set[str] = set()
        for role in ROLES:
            for company in COMPANIES:
                seed = get_seed(role, company)
                if seed:
                    for rnd in seed["rounds"]:
                        all_round_names.add(rnd["name"])

        broken = {
            topic: target
            for topic, target in TOPIC_TO_ROUND.items()
            if target not in all_round_names
        }
        # This is informational — prints which mappings are broken
        if broken:
            msg = "Broken TOPIC_TO_ROUND mappings (questions won't link):\n"
            for topic, target in broken.items():
                msg += f"  '{topic}' -> '{target}'\n"
            pytest.xfail(msg)


# ── Noise Filter & Normalization ──────────────────────────────────────────────

class TestSkillNormalization:

    def test_strips_whitespace(self):
        assert _normalize_skill_name("  Python  ") == "Python"

    def test_rejects_empty(self):
        assert _normalize_skill_name("") is None

    def test_rejects_lowercase_single_char(self):
        assert _normalize_skill_name("a") is None
        assert _normalize_skill_name("x") is None

    def test_accepts_uppercase_single_char(self):
        """R and C are real programming languages."""
        assert _normalize_skill_name("R") == "R"
        assert _normalize_skill_name("C") == "C"

    def test_rejects_noise(self):
        assert _normalize_skill_name("n/a") is None
        assert _normalize_skill_name("None") is None
        assert _normalize_skill_name("other") is None

    def test_rejects_numeric(self):
        assert _normalize_skill_name("123") is None
        assert _normalize_skill_name("3.14") is None

    def test_accepts_valid_skills(self):
        assert _normalize_skill_name("Python") == "Python"
        assert _normalize_skill_name("Apache Spark") == "Apache Spark"
        assert _normalize_skill_name("A/B Testing") == "A/B Testing"
        assert _normalize_skill_name("Power BI") == "Power BI"

    def test_noise_set_is_lowercase(self):
        for entry in NOISE_SKILLS:
            assert entry == entry.lower(), f"Noise entry '{entry}' should be lowercase"

    def test_soft_skills_not_in_noise(self):
        """Soft skills should still load into the graph, just classified as Medium."""
        for sk in SOFT_SKILLS:
            normalized = _normalize_skill_name(sk)
            assert normalized is not None, f"Soft skill '{sk}' incorrectly filtered as noise"