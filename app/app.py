"""
Prismiq — AI-Powered Interview Preparation Platform
Streamlit UI with Dashboard, Practice Mode, and KG Chat.
Production-grade interface.
"""

from __future__ import annotations

import html as html_lib
import logging
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from config import COMPANY_COLORS, ROLES, setup_logging
from kg.schema import get_driver
from kg.kg_retrieval import (
    get_company_overview,
    get_questions_by_level,
    get_all_rounds,
    get_context_for_generation,
    get_companies,
    get_roles,
    get_experience_levels,
    get_companies_for_role,
)
from kg.kg_chat import route_query
from llm.chat import answer_from_kg
from llm.generator import generate_question
from llm.evaluator import evaluate_answer, explain_reasoning_path
from llm.round_filter import filter_rounds_by_level

# Import the authoritative skill classification from the KG loader
from kg.load_kg import CRITICAL_BY_COMPANY_ROLE, SOFT_SKILLS

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Prismiq — Interview Prep",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System ────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --pri:        #0D9373;
    --pri-light:  #E6F7F2;
    --pri-dark:   #085C4A;
    --accent:     #6366F1;
    --accent-lt:  #EEF2FF;
    --bg:         #FFFFFF;
    --bg-sub:     #F8FAFB;
    --bg-card:    #FFFFFF;
    --border:     #E5E7EB;
    --border-lt:  #F1F3F5;
    --text:       #111827;
    --text-2:     #4B5563;
    --text-3:     #9CA3AF;
    --red:        #EF4444;
    --red-bg:     #FEF2F2;
    --amber:      #F59E0B;
    --amber-bg:   #FFFBEB;
    --green:      #10B981;
    --green-bg:   #ECFDF5;
    --radius:     10px;
    --radius-lg:  14px;
    --shadow-sm:  0 1px 2px rgba(0,0,0,.04), 0 1px 3px rgba(0,0,0,.06);
    --shadow:     0 1px 3px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.04);
    --shadow-md:  0 4px 6px rgba(0,0,0,.04), 0 10px 24px rgba(0,0,0,.06);
}

section[data-testid="stSidebar"] {
    background: #F8FAFB;
    border-right: 1px solid var(--border);
}

.block-container { padding-top: 2rem !important; max-width: 1200px; }

/* ── Page Header ──────────────────────────────────────────────── */
.page-header {
    margin-bottom: 1.8rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--border-lt);
}
.page-header h1 {
    font-family: 'Inter', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 .25rem 0;
    letter-spacing: -0.02em;
}
.page-header .subtitle {
    font-family: 'Inter', sans-serif;
    font-size: .92rem;
    color: var(--text-3);
    margin: 0;
}
.page-header .context-chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: .78rem;
    font-weight: 500;
    margin-right: 6px;
    margin-top: 8px;
}
.chip-company { background: var(--pri-light); color: var(--pri-dark); }
.chip-role    { background: var(--accent-lt); color: var(--accent); }
.chip-level   { background: #F3F4F6; color: var(--text-2); }

/* ── Metric Cards ─────────────────────────────────────────────── */
.metric-row { display: flex; gap: 14px; margin: 1.2rem 0; }
.metric-card {
    flex: 1;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    box-shadow: var(--shadow-sm);
    transition: box-shadow .2s;
}
.metric-card:hover { box-shadow: var(--shadow); }
.metric-card .label {
    font-family: 'Inter', sans-serif;
    font-size: .78rem; font-weight: 500;
    text-transform: uppercase; letter-spacing: .04em;
    color: var(--text-3); margin: 0 0 4px 0;
}
.metric-card .value {
    font-family: 'Inter', sans-serif;
    font-size: 1.6rem; font-weight: 700;
    color: var(--text); margin: 0;
}
.metric-card .value.green { color: var(--green); }

/* ── Section Heading ──────────────────────────────────────────── */
.section-heading {
    font-family: 'Inter', sans-serif;
    font-size: 1rem; font-weight: 600; color: var(--text);
    margin: 2rem 0 .8rem 0;
    display: flex; align-items: center; gap: 8px;
}
.section-heading .count {
    font-size: .78rem; font-weight: 500; color: var(--text-3);
    background: var(--bg-sub); border: 1px solid var(--border);
    border-radius: 20px; padding: 1px 10px;
}

/* ── Round Cards ──────────────────────────────────────────────── */
.round-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px; margin-bottom: 1rem;
}
.round-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 18px;
    box-shadow: var(--shadow-sm);
    border-left: 3px solid var(--pri);
    transition: transform .15s, box-shadow .15s;
}
.round-card:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
.round-card .round-num {
    font-family: 'Inter', sans-serif;
    font-size: .7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em;
    color: var(--pri); margin: 0 0 4px 0;
}
.round-card .round-name {
    font-family: 'Inter', sans-serif;
    font-size: .92rem; font-weight: 600;
    color: var(--text); margin: 0 0 8px 0; line-height: 1.3;
}
.round-card .round-meta { font-size: .78rem; color: var(--text-3); }
.round-card .round-meta span { margin-right: 10px; }

/* ── Skill Badges ─────────────────────────────────────────────── */
.skill-section {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow-sm); margin-bottom: 12px;
}
.skill-section .skill-title {
    font-family: 'Inter', sans-serif;
    font-size: .82rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .04em;
    margin: 0 0 12px 0;
}
.skill-title.critical { color: var(--red); }
.skill-title.good     { color: var(--green); }
.skill-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.skill-pill {
    display: inline-flex; align-items: center;
    padding: 5px 13px; border-radius: 20px;
    font-family: 'Inter', sans-serif;
    font-size: .8rem; font-weight: 500;
    transition: transform .1s;
}
.skill-pill:hover { transform: scale(1.04); }
.pill-critical { background: var(--red-bg); color: #991B1B; border: 1px solid #FECACA; }
.pill-high     { background: var(--amber-bg); color: #92400E; border: 1px solid #FDE68A; }
.pill-good     { background: var(--green-bg); color: #065F46; border: 1px solid #A7F3D0; }

/* ── Question Card ────────────────────────────────────────────── */
.question-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 24px;
    box-shadow: var(--shadow); margin: 1rem 0;
}
.question-card .q-meta { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.q-tag {
    display: inline-flex; align-items: center;
    padding: 3px 10px; border-radius: 6px;
    font-family: 'Inter', sans-serif; font-size: .75rem; font-weight: 500;
}
.q-tag.round       { background: var(--pri-light); color: var(--pri-dark); }
.q-tag.diff-easy   { background: var(--green-bg); color: #065F46; }
.q-tag.diff-medium { background: var(--amber-bg); color: #92400E; }
.q-tag.diff-hard   { background: var(--red-bg);   color: #991B1B; }
.q-tag.skill       { background: #F3F4F6; color: var(--text-2); }
.question-card .q-text {
    font-family: 'Inter', sans-serif;
    font-size: 1.05rem; font-weight: 500;
    color: var(--text); line-height: 1.6; margin: 0;
    white-space: pre-wrap;
}

/* ── Score Display ────────────────────────────────────────────── */
.score-ring { position: relative; width: 90px; height: 90px; }
.score-ring svg { transform: rotate(-90deg); }
.score-ring .score-text {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 700;
}
.score-text.high { color: var(--green); }
.score-text.mid  { color: var(--amber); }
.score-text.low  { color: var(--red); }

.eval-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px;
    box-shadow: var(--shadow-sm); margin-bottom: 12px;
}
.eval-card .eval-title {
    font-family: 'Inter', sans-serif;
    font-size: .82rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .04em;
    margin: 0 0 10px 0;
}
.eval-card .eval-title.strengths { color: var(--green); }
.eval-card .eval-title.gaps      { color: var(--red); }
.eval-card .eval-title.next      { color: var(--accent); }
.eval-card ul { margin: 0; padding-left: 18px; }
.eval-card li {
    font-family: 'Inter', sans-serif; font-size: .88rem;
    color: var(--text-2); margin-bottom: 5px; line-height: 1.5;
}

/* ── Reasoning Path ───────────────────────────────────────────── */
.reasoning-box {
    background: linear-gradient(135deg, var(--pri-light) 0%, #F0F9FF 100%);
    border: 1px solid #A7F3D0; border-radius: var(--radius);
    padding: 18px 20px; margin-top: 1rem;
}
.reasoning-box .reasoning-title {
    font-family: 'Inter', sans-serif; font-size: .85rem;
    font-weight: 600; color: var(--pri-dark); margin: 0 0 6px 0;
}
.reasoning-box .reasoning-path {
    font-family: 'Inter', sans-serif; font-size: .78rem;
    color: var(--pri); margin: 0 0 10px 0; font-weight: 500;
}
.reasoning-box .reasoning-text {
    font-family: 'Inter', sans-serif; font-size: .88rem;
    color: var(--text-2); line-height: 1.55; margin: 0;
}

/* ── Hint ─────────────────────────────────────────────────────── */
.hint-item {
    background: var(--amber-bg); border-left: 3px solid var(--amber);
    border-radius: 0 8px 8px 0; padding: 8px 14px; margin-bottom: 6px;
    font-family: 'Inter', sans-serif; font-size: .85rem; color: #92400E;
}

/* ── KG Chat ──────────────────────────────────────────────────── */
.chat-container { max-width: 820px; margin: 0 auto; }
.chat-msg { margin-bottom: 16px; display: flex; gap: 10px; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.bot  { justify-content: flex-start; }
.chat-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .8rem; font-weight: 700; flex-shrink: 0;
}
.chat-avatar.user-av { background: var(--accent-lt); color: var(--accent); }
.chat-avatar.bot-av  { background: var(--pri-light);  color: var(--pri); }
.chat-bubble {
    max-width: 75%; padding: 12px 16px; border-radius: 14px;
    font-family: 'Inter', sans-serif; font-size: .9rem; line-height: 1.55;
}
.chat-bubble.user-bubble {
    background: var(--accent); color: white; border-bottom-right-radius: 4px;
}
.chat-bubble.bot-bubble {
    background: var(--bg-sub); border: 1px solid var(--border);
    color: var(--text); border-bottom-left-radius: 4px;
}
.kg-source-box {
    background: #F9FAFB; border: 1px solid var(--border);
    border-radius: var(--radius); padding: 14px;
    margin-top: 8px; margin-left: 42px; max-width: 75%;
}
.kg-source-header { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.kg-badge {
    background: var(--pri-light); color: var(--pri-dark);
    border-radius: 4px; padding: 2px 7px;
    font-size: .7rem; font-weight: 600; letter-spacing: .03em;
}
.kg-source-desc { font-family: 'Inter', sans-serif; font-size: .82rem; font-weight: 500; color: var(--text); }
.kg-source-rows { font-size: .75rem; color: var(--text-3); }
.cypher-block {
    background: #1E293B; color: #E2E8F0; border-radius: 8px;
    padding: 12px 14px; font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: .75rem; line-height: 1.5; margin-top: 8px;
    white-space: pre-wrap; overflow-x: auto;
}

/* ── Sidebar ──────────────────────────────────────────────────── */
.sidebar-brand {
    font-family: 'Inter', sans-serif; font-size: 1.3rem;
    font-weight: 700; color: var(--pri-dark); letter-spacing: -0.02em;
    margin-bottom: 2px;
}
.sidebar-tagline {
    font-family: 'Inter', sans-serif; font-size: .75rem;
    color: var(--text-3); margin-bottom: 1.2rem;
}
.sidebar-context {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 12px; margin-top: 12px;
    font-family: 'Inter', sans-serif; font-size: .82rem;
    color: var(--text-2); line-height: 1.4;
}

/* ── Button / Input Overrides ─────────────────────────────────── */
div[data-testid="stTextArea"] textarea {
    border-radius: var(--radius) !important;
    border-color: var(--border) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: .9rem !important; line-height: 1.55 !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--pri) !important;
    box-shadow: 0 0 0 2px rgba(13,147,115,.15) !important;
}
.stButton > button[kind="primary"] {
    background: var(--pri) !important; border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important; font-weight: 600 !important;
    padding: 8px 20px !important;
}
.stButton > button[kind="primary"]:hover { background: var(--pri-dark) !important; }
.stButton > button[kind="secondary"], .stButton > button:not([kind]) {
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important; font-weight: 500 !important;
    border-color: var(--border) !important;
}
div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; overflow: hidden;
}
</style>
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _esc(text) -> str:
    """HTML-escape user/KG text to prevent injection."""
    return html_lib.escape(str(text)) if text else ""


def _page_header(title: str, subtitle: str, company: str = "", role: str = "", level: str = ""):
    chips = ""
    if company:
        chips += f'<span class="context-chip chip-company">{_esc(company)}</span>'
    if role:
        chips += f'<span class="context-chip chip-role">{_esc(role)}</span>'
    if level:
        chips += f'<span class="context-chip chip-level">{_esc(level)}</span>'
    st.markdown(
        f'<div class="page-header">'
        f'  <h1>{_esc(title)}</h1>'
        f'  <p class="subtitle">{_esc(subtitle)}</p>'
        f'  {chips}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _section(title: str, count: int | None = None):
    count_html = f'<span class="count">{count}</span>' if count is not None else ""
    st.markdown(
        f'<div class="section-heading">{_esc(title)}{count_html}</div>',
        unsafe_allow_html=True,
    )


def _metric_row(metrics: list[tuple[str, str | int, bool]]):
    cards = ""
    for label, value, green in metrics:
        cls = ' green' if green else ''
        cards += (
            f'<div class="metric-card">'
            f'  <p class="label">{_esc(str(label))}</p>'
            f'  <p class="value{cls}">{_esc(str(value))}</p>'
            f'</div>'
        )
    st.markdown(f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True)


def _score_ring_svg(score: int) -> str:
    r = 36
    circ = 2 * 3.14159 * r
    offset = circ * (1 - score / 10)
    if score >= 8:
        color, cls = "#10B981", "high"
    elif score >= 5:
        color, cls = "#F59E0B", "mid"
    else:
        color, cls = "#EF4444", "low"
    return (
        f'<div class="score-ring">'
        f'  <svg width="90" height="90" viewBox="0 0 90 90">'
        f'    <circle cx="45" cy="45" r="{r}" fill="none" stroke="#E5E7EB" stroke-width="6"/>'
        f'    <circle cx="45" cy="45" r="{r}" fill="none" stroke="{color}" '
        f'            stroke-width="6" stroke-linecap="round" '
        f'            stroke-dasharray="{circ}" stroke-dashoffset="{offset}"/>'
        f'  </svg>'
        f'  <span class="score-text {cls}">{score}</span>'
        f'</div>'
    )


def _difficulty_class(diff: str) -> str:
    d = (diff or "Medium").lower()
    if d == "easy":
        return "diff-easy"
    if d == "hard":
        return "diff-hard"
    return "diff-medium"


def _reclassify_skills(skills: list[dict], company: str, role: str) -> list[dict]:
    """
    Post-process skills from the KG using the authoritative
    CRITICAL_BY_COMPANY_ROLE mapping defined in load_kg.py.

    This ensures the dashboard always shows the correct Critical vs
    Good-to-Have breakdown regardless of what importance value is
    stored on the NEEDS relationship in Neo4j.
    """
    critical_set = CRITICAL_BY_COMPANY_ROLE.get((company, role), set())
    for s in skills:
        name = s.get("name", "")
        if name in critical_set:
            s["importance"] = "Critical"
        elif name in SOFT_SKILLS:
            s["importance"] = "Medium"
        # Keep existing High/Medium if not in critical or soft
    return skills


# ── Driver ───────────────────────────────────────────────────────────────────

@st.cache_resource
def _init_driver():
    try:
        driver = get_driver()
        driver.verify_connectivity()
        logger.info("Neo4j connected")
        return driver
    except Exception:
        logger.exception("Neo4j connection failed")
        return None


# ── Sidebar ──────────────────────────────────────────────────────────────────

def _sidebar(driver):
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand">Prismiq</div>'
            '<div class="sidebar-tagline">Knowledge Graph + LLM Interview Prep</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        page = st.radio(
            "Navigate",
            ["Dashboard", "Practice Mode", "KG Chat"],
            label_visibility="collapsed",
        )
        st.markdown("---")

        roles = get_roles(driver) if driver else ROLES
        role = st.selectbox("Role", roles)
        companies = (get_companies_for_role(driver, role) or get_companies(driver)) if driver else []
        company = st.selectbox("Company", companies)
        levels = get_experience_levels(driver) if driver else ["Entry", "Mid", "Senior"]
        experience = st.selectbox("Experience Level", levels)

        color = COMPANY_COLORS.get(company, "#4285F4")
        st.markdown(
            f'<div class="sidebar-context">'
            f'  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'  background:{color};margin-right:6px;vertical-align:middle;"></span>'
            f'  <strong>{_esc(company)}</strong> · {_esc(role)} · {_esc(experience)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    return page, company, role, experience


# ── Dashboard ────────────────────────────────────────────────────────────────

def _dashboard(driver, company, role, experience):
    _page_header(
        f"{company} Interview Guide",
        "Company-specific preparation powered by Knowledge Graph data",
        company, role, experience,
    )

    overview = get_company_overview(driver, company, role)

    # Reclassify skills using the authoritative source-of-truth mapping
    overview["skills"] = _reclassify_skills(overview["skills"], company, role)

    # Filter rounds by experience level
    filtered_rounds = filter_rounds_by_level(company, role, experience, overview["rounds"])
    for idx, r in enumerate(filtered_rounds, 1):
        r["round_order"] = idx

    questions = get_questions_by_level(driver, company, experience, role)
    critical = [s for s in overview["skills"] if s["importance"] == "Critical"]
    other = [s for s in overview["skills"] if s["importance"] in ("Medium", "High")]

    # Metrics
    _metric_row([
        ("Rounds", len(filtered_rounds), False),
        ("Total Skills", len(overview["skills"]), False),
        ("Critical Skills", len(critical), True),
        (f"Questions ({experience})", len(questions), False),
    ])

    # Rounds
    _section("Interview Rounds", len(filtered_rounds))

    if filtered_rounds:
        color = COMPANY_COLORS.get(company, "#4285F4")
        cards_html = '<div class="round-grid">'
        for r in filtered_rounds:
            qtypes = r.get("question_types") or []
            skills_str = _esc(", ".join(qtypes[:2])) if qtypes else ""
            duration = r.get("duration") or r.get("duration_min") or "?"
            cards_html += (
                f'<div class="round-card" style="border-left-color:{color};">'
                f'  <p class="round-num">Round {r["round_order"]}</p>'
                f'  <p class="round-name">{_esc(r["name"])}</p>'
                f'  <p class="round-meta"><span>{duration} min</span></p>'
                f'  {"<p class=round-meta>" + skills_str + "</p>" if skills_str else ""}'
                f'</div>'
            )
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)
    else:
        st.info(f"No round data available for {role} at {company}.")

    # Skills
    _section("Required Skills")
    col1, col2 = st.columns(2)

    with col1:
        pills = "".join(
            f'<span class="skill-pill pill-critical">{_esc(s["name"])}</span>'
            for s in critical
        )
        st.markdown(
            f'<div class="skill-section">'
            f'  <p class="skill-title critical">Must-Have · {len(critical)} skills</p>'
            f'  <div class="skill-pills">{pills or "<span style=color:var(--text-3);font-size:.85rem>None identified</span>"}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col2:
        pills_h = "".join(
            f'<span class="skill-pill pill-high">{_esc(s["name"])}</span>'
            for s in other if s["importance"] == "High"
        )
        pills_m = "".join(
            f'<span class="skill-pill pill-good">{_esc(s["name"])}</span>'
            for s in other if s["importance"] == "Medium"
        )
        st.markdown(
            f'<div class="skill-section">'
            f'  <p class="skill-title good">Good-to-Have · {len(other)} skills</p>'
            f'  <div class="skill-pills">{pills_h}{pills_m}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Practice Mode ────────────────────────────────────────────────────────────

def _practice(driver, company, role, experience):
    _page_header(
        "Practice Mode",
        "Generate targeted questions, answer, and get AI-powered feedback",
        company, role, experience,
    )

    all_rounds = get_all_rounds(driver, company, role)
    rounds = filter_rounds_by_level(company, role, experience, all_rounds)
    names = ["Random"] + [r["name"] for r in rounds]
    selected = st.selectbox("Interview Round", names)
    actual = random.choice([r["name"] for r in rounds]) if selected == "Random" and rounds else selected

    for key in ("current_question", "feedback", "reasoning"):
        if key not in st.session_state:
            st.session_state[key] = None
    if "practice_history" not in st.session_state:
        st.session_state.practice_history = []

    col_g, col_h = st.columns([4, 1])
    with col_g:
        if st.button("Generate Question", type="primary", use_container_width=True):
            with st.spinner("Querying KG and generating question..."):
                ctx = get_context_for_generation(driver, company, role, experience, actual)
                q = generate_question(company, role, experience, actual, ctx)
                st.session_state.update(
                    current_question=q, kg_context=ctx,
                    actual_round=actual, feedback=None, reasoning=None,
                )
    with col_h:
        practiced = len(st.session_state.practice_history)
        st.markdown(
            f'<div class="metric-card" style="text-align:center;padding:10px 14px;">'
            f'  <p class="label">Practiced</p>'
            f'  <p class="value green">{practiced}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    q = st.session_state.current_question
    if not q:
        st.markdown(
            '<div style="text-align:center;padding:3rem 1rem;color:#9CA3AF;">'
            '<p style="font-size:.95rem;">Select a round and generate a question to start practicing.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Question card
    diff = q.get("difficulty", "Medium")
    skills_tags = "".join(
        f'<span class="q-tag skill">{_esc(s)}</span>' for s in q.get("skills_tested", [])
    )
    st.markdown(
        f'<div class="question-card">'
        f'  <div class="q-meta">'
        f'    <span class="q-tag round">{_esc(q.get("round", actual))}</span>'
        f'    <span class="q-tag {_difficulty_class(diff)}">{_esc(diff)}</span>'
        f'    {skills_tags}'
        f'  </div>'
        f'  <p class="q-text">{_esc(q["question"])}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if q.get("hints"):
        with st.expander("Hints"):
            hints_html = "".join(
                f'<div class="hint-item"><strong>{i}.</strong> {_esc(h)}</div>'
                for i, h in enumerate(q["hints"], 1)
            )
            st.markdown(hints_html, unsafe_allow_html=True)

    answer = st.text_area(
        "Your Answer", height=180,
        placeholder="Type your answer here...",
        key="answer_input",
    )

    c1, c2 = st.columns(2)
    with c1:
        eval_btn = st.button("Evaluate Answer", type="primary", use_container_width=True)
    with c2:
        skip_btn = st.button("Skip / Next", use_container_width=True)

    if skip_btn:
        with st.spinner("Generating next question..."):
            ctx = get_context_for_generation(driver, company, role, experience, actual)
            nq = generate_question(company, role, experience, actual, ctx)
            st.session_state.update(current_question=nq, kg_context=ctx, feedback=None, reasoning=None)
            st.rerun()

    if eval_btn:
        if not answer.strip():
            st.warning("Please enter an answer before evaluating.")
            return
        with st.spinner("Evaluating your answer..."):
            ctx = st.session_state.get("kg_context", {})
            fb = evaluate_answer(company, q["question"], answer, ctx, q.get("round", actual), experience, role)
            st.session_state.feedback = fb
            ri = next(
                (r for r in rounds if r["name"] == q.get("round", actual)),
                {"name": actual, "round_order": 1},
            )
            st.session_state.reasoning = explain_reasoning_path(
                company, ri["name"], ri.get("round_order", 1), q.get("skills_tested", []), role,
            )
            st.session_state.practice_history.append({
                "question": q["question"], "score": fb["score"],
                "round": q.get("round", actual), "role": role,
            })

    fb = st.session_state.feedback
    if not fb:
        return

    st.markdown("---")
    _section("Evaluation Results")

    score = fb["score"]
    sc_col, detail_col = st.columns([1, 3])
    with sc_col:
        st.markdown(_score_ring_svg(score), unsafe_allow_html=True)
        label = "Excellent" if score >= 8 else "Good Progress" if score >= 5 else "Keep Practicing"
        clr = "var(--green)" if score >= 8 else "var(--amber)" if score >= 5 else "var(--red)"
        st.markdown(
            f'<p style="text-align:center;font-family:Inter,sans-serif;font-size:.82rem;'
            f'font-weight:600;color:{clr};margin-top:4px;">{label}</p>',
            unsafe_allow_html=True,
        )
    with detail_col:
        strengths_li = "".join(f"<li>{_esc(s)}</li>" for s in fb.get("strengths", []))
        st.markdown(
            f'<div class="eval-card">'
            f'  <p class="eval-title strengths">Strengths</p>'
            f'  <ul>{strengths_li}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )
        gaps_li = "".join(f"<li>{_esc(g)}</li>" for g in fb.get("gaps", []))
        st.markdown(
            f'<div class="eval-card">'
            f'  <p class="eval-title gaps">Areas for Improvement</p>'
            f'  <ul>{gaps_li}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.expander("Model Answer"):
        st.markdown(fb.get("ideal_answer", ""))

    col_sk, col_ns = st.columns(2)
    with col_sk:
        if fb.get("skills_to_improve"):
            pills = "".join(
                f'<span class="skill-pill pill-critical">{_esc(sk)}</span>'
                for sk in fb["skills_to_improve"]
            )
            st.markdown(
                f'<div class="eval-card">'
                f'  <p class="eval-title gaps">Skills to Improve</p>'
                f'  <div class="skill-pills">{pills}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with col_ns:
        if fb.get("next_steps"):
            steps_li = "".join(f"<li>{_esc(ns)}</li>" for ns in fb["next_steps"])
            st.markdown(
                f'<div class="eval-card">'
                f'  <p class="eval-title next">Next Steps</p>'
                f'  <ul>{steps_li}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if fb.get("recommended_resources"):
        with st.expander("Recommended Resources"):
            for r in fb["recommended_resources"]:
                st.markdown(f"- {r}")

    if st.session_state.reasoning:
        skills_str = " > ".join(q.get("skills_tested", []))
        st.markdown(
            f'<div class="reasoning-box">'
            f'  <p class="reasoning-title">Why This Question?</p>'
            f'  <p class="reasoning-path">{_esc(company)} > {_esc(q.get("round", actual))} > {_esc(skills_str)}</p>'
            f'  <p class="reasoning-text">{_esc(st.session_state.reasoning)}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── KG Chat ──────────────────────────────────────────────────────────────────

def _kg_chat(driver, company, role):
    _page_header(
        "KG Chat",
        "Ask anything about interviews — every answer is traced back to the Knowledge Graph",
    )

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if not st.session_state.chat_history:
        suggestions = [
            f"What rounds does {company} have for {role}?",
            f"What skills do I need for {role} at {company}?",
            f"Compare Google vs Amazon for Data Engineer",
            f"Show me sample SQL questions for Meta",
            f"How do I prepare for System Design at Netflix?",
        ]
        st.markdown(
            '<p style="font-family:Inter,sans-serif;font-size:.85rem;color:#9CA3AF;'
            'margin-bottom:10px;">Try asking:</p>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(suggestions))
        for i, sug in enumerate(suggestions):
            with cols[i]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.chat_input_value = sug

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-msg user">'
                f'  <div class="chat-bubble user-bubble">{_esc(msg["content"])}</div>'
                f'  <div class="chat-avatar user-av">Y</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="chat-msg bot">'
                f'  <div class="chat-avatar bot-av">P</div>'
                f'  <div class="chat-bubble bot-bubble">{_esc(msg["content"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if msg.get("kg_results"):
                with st.expander(
                    f"KG Sources — {len(msg['kg_results'])} quer{'y' if len(msg['kg_results']) == 1 else 'ies'}"
                ):
                    for result in msg["kg_results"]:
                        st.markdown(
                            f'<div class="kg-source-box">'
                            f'  <div class="kg-source-header">'
                            f'    <span class="kg-badge">KG</span>'
                            f'    <span class="kg-source-desc">{_esc(result["description"])}</span>'
                            f'    <span class="kg-source-rows"> · {result["row_count"]} rows</span>'
                            f'  </div>'
                            f'  <div class="cypher-block">{_esc(result["cypher"])}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    st.markdown('</div>', unsafe_allow_html=True)

    prefill = st.session_state.pop("chat_input_value", "")
    user_input = st.chat_input("Ask about any company, role, round, or skill...")

    if prefill and not user_input:
        user_input = prefill

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Querying Knowledge Graph..."):
            all_companies = get_companies(driver)
            all_roles = get_roles(driver)
            kg_results = route_query(
                driver=driver, query=user_input,
                companies=all_companies, roles=all_roles,
                default_company=company, default_role=role,
            )
            answer = answer_from_kg(user_input, kg_results)
            result_summaries = [
                {
                    "description": r.description,
                    "row_count": len(r.data),
                    "cypher": r.runnable_cypher,
                }
                for r in kg_results
            ]

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "kg_results": result_summaries,
        })
        st.rerun()

    if st.session_state.chat_history:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear conversation"):
            st.session_state.chat_history = []
            st.rerun()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    st.markdown(_CSS, unsafe_allow_html=True)
    driver = _init_driver()

    if driver is None:
        st.error(
            "**Cannot connect to Neo4j.**  \n"
            "Make sure Neo4j is running and your `.env` has the correct credentials."
        )
        st.code("NEO4J_URI=bolt://localhost:7687\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=your-password")
        st.stop()

    page, company, role, experience = _sidebar(driver)

    try:
        if page == "Dashboard":
            _dashboard(driver, company, role, experience)
        elif page == "Practice Mode":
            _practice(driver, company, role, experience)
        elif page == "KG Chat":
            _kg_chat(driver, company, role)
    except Exception:
        logger.exception("Unhandled error in %s", page)
        st.error("Something went wrong. Check the logs for details.")


if __name__ == "__main__":
    main()