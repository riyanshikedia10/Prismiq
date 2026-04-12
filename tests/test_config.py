"""Smoke tests for configuration and models."""

from config import ROLES, ROLE_SLUGS, COMPANIES, EXPERIENCE_LEVELS
from models import Skill, InterviewQuestion, GeneratedQuestion, EvaluationResult, CompanyData
from llm.seeds import SEED_DATA, get_seed, get_companies_for_role


def test_roles_have_slugs():
    for role in ROLES:
        assert role in ROLE_SLUGS, f"Missing slug for {role}"


def test_all_companies_have_aliases():
    from config import COMPANY_ALIASES
    for company in COMPANIES:
        assert company in COMPANY_ALIASES, f"Missing aliases for {company}"


def test_seed_data_covers_all_roles():
    for role in ROLES:
        companies = get_companies_for_role(role)
        assert len(companies) >= 5, f"{role} has only {len(companies)} companies"


def test_seed_rounds_are_ordered():
    for role, companies in SEED_DATA.items():
        for company, data in companies.items():
            orders = [r["order"] for r in data["rounds"]]
            assert orders == sorted(orders), f"Rounds out of order: {role}/{company}"


def test_skill_model_validates():
    s = Skill(name="  Python  ", category="Technical", importance="Critical")
    assert s.name == "Python"


def test_skill_model_rejects_empty():
    import pytest
    with pytest.raises(Exception):
        Skill(name="", category="Technical")


def test_question_model_validates():
    q = InterviewQuestion(text="What is SQL?", round="Technical", difficulty="Easy")
    assert q.difficulty == "Easy"


def test_generated_question_defaults():
    gq = GeneratedQuestion(question="Explain X")
    assert gq.difficulty == "Medium"
    assert gq.hints == []


def test_evaluation_result_clamps_score():
    import pytest
    with pytest.raises(Exception):
        EvaluationResult(score=11)


def test_company_data_validates():
    cd = CompanyData(rounds=[], skills=[], sample_questions=[], learning_resources=[])
    assert len(cd.rounds) == 0
