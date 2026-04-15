"""
Prismiq — AI-Powered Interview Preparation Platform
Streamlit UI with Dashboard, Practice Mode, and KG Chat.
"""

from __future__ import annotations

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

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Prismiq", layout="wide", initial_sidebar_state="expanded")

_CSS = """
<style>
.main-header { font-size:2.2rem; font-weight:700; margin-bottom:.2rem; }
.sub-header  { color:#888; font-size:1.05rem; margin-bottom:1.5rem; }
.score-high  { color:#28a745; font-size:2.5rem; font-weight:bold; }
.score-mid   { color:#ffc107; font-size:2.5rem; font-weight:bold; }
.score-low   { color:#dc3545; font-size:2.5rem; font-weight:bold; }
.skill-badge { display:inline-block; padding:4px 12px; border-radius:16px; font-size:.85rem; margin:3px 4px; font-weight:500; }
.badge-critical { background:#ffe0e0; color:#c0392b; }
.badge-medium   { background:#d4edda; color:#155724; }
.round-card { background:#f8f9fa; border-radius:10px; padding:16px; margin-bottom:12px; border-left:4px solid #4285F4; }
.chat-user { background:#e8f4fd; border-radius:12px; padding:12px 16px; margin:8px 0; }
.chat-bot  { background:#f8f9fa; border-radius:12px; padding:12px 16px; margin:8px 0; border-left:3px solid #1D9E75; }
.cypher-box { background:#1e1e1e; color:#d4d4d4; border-radius:8px; padding:12px; font-family:monospace; font-size:12px; margin-top:8px; white-space:pre-wrap; }
.kg-badge { background:#e1f5ee; color:#085041; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:500; }
</style>
"""


# ── Driver ────────────────────────────────────────────────────────────────────

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


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _sidebar(driver):
    with st.sidebar:
        st.markdown("## Prismiq")
        st.caption("KG + LLM Interview Prep")
        st.markdown("---")

        page = st.radio(
            "Navigate",
            ["Dashboard", "Practice Mode", "KG Chat"],
            label_visibility="collapsed",
        )
        st.markdown("---")

        roles     = get_roles(driver) if driver else ROLES
        role      = st.selectbox("Role", roles)
        companies = (get_companies_for_role(driver, role) or get_companies(driver)) if driver else []
        company   = st.selectbox("Company", companies)
        levels    = get_experience_levels(driver) if driver else ["Entry", "Mid", "Senior"]
        experience = st.selectbox("Experience Level", levels)

        st.markdown("---")
        st.markdown(f"**{company} / {role} / {experience}**")

    return page, company, role, experience


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _dashboard(driver, company, role, experience):
    st.markdown(f'<div class="main-header">{company} — {role}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Experience: {experience} | KG + GPT-4o-mini</div>', unsafe_allow_html=True)

    overview = get_company_overview(driver, company, role)

    # Filter rounds by experience level using LLM
    filtered_rounds = filter_rounds_by_level(company, role, experience, overview["rounds"])
    # Re-number rounds sequentially after filtering
    for idx, r in enumerate(filtered_rounds, 1):
        r["round_order"] = idx

    st.markdown(f"### Interview Rounds ({len(filtered_rounds)} for {experience} level)")
    if filtered_rounds:
        cols = st.columns(min(len(filtered_rounds), 3))
        for i, r in enumerate(filtered_rounds):
            with cols[i % len(cols)]:
                color = COMPANY_COLORS.get(company, "#4285F4")
                st.markdown(
                    f'<div class="round-card" style="border-left-color:{color};">'
                    f'<strong>Round {r["round_order"]}</strong>: {r["name"]}<br>'
                    f'<small>{r.get("duration","?")} min</small></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info(f"No round data for {role} at {company}.")

    st.markdown("### Required Skills")
    critical = [s for s in overview["skills"] if s["importance"] == "Critical"]
    medium   = [s for s in overview["skills"] if s["importance"] in ("Medium", "High")]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Must have**")
        for s in critical:
            st.markdown(f'<span class="skill-badge badge-critical">{s["name"]}</span>', unsafe_allow_html=True)
    with c2:
        st.markdown("**Good to have**")
        for s in medium:
            st.markdown(f'<span class="skill-badge badge-medium">{s["name"]}</span>', unsafe_allow_html=True)

    st.markdown("### Quick Stats")
    questions = get_questions_by_level(driver, company, experience, role)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rounds",                   len(filtered_rounds))
    m2.metric("Skills",                   len(overview["skills"]))
    m3.metric(f"Questions ({experience})", len(questions))
    m4.metric("Critical Skills",           len(critical))


# ── Practice ──────────────────────────────────────────────────────────────────

def _practice(driver, company, role, experience):
    st.markdown(f'<div class="main-header">Practice Mode — {role}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">{company} / {role} / {experience}</div>', unsafe_allow_html=True)

    all_rounds = get_all_rounds(driver, company, role)
    rounds     = filter_rounds_by_level(company, role, experience, all_rounds)
    names      = ["Random"] + [r["name"] for r in rounds]
    selected = st.selectbox("Interview Round", names)
    actual   = random.choice([r["name"] for r in rounds]) if selected == "Random" and rounds else selected

    for key in ("current_question", "feedback", "reasoning"):
        if key not in st.session_state:
            st.session_state[key] = None
    if "practice_history" not in st.session_state:
        st.session_state.practice_history = []

    col_g, col_h = st.columns([3, 1])
    with col_g:
        if st.button("Generate Question", type="primary", use_container_width=True):
            with st.spinner("Generating..."):
                ctx = get_context_for_generation(driver, company, role, experience, actual)
                q   = generate_question(company, role, experience, actual, ctx)
                st.session_state.update(
                    current_question=q, kg_context=ctx,
                    actual_round=actual, feedback=None, reasoning=None,
                )
    with col_h:
        st.metric("Practiced", len(st.session_state.practice_history))

    q = st.session_state.current_question
    if not q:
        return

    st.markdown("---")
    st.markdown(
        f"**Round:** {q.get('round', actual)} | "
        f"**Difficulty:** {q.get('difficulty')} | "
        f"**Skills:** {', '.join(q.get('skills_tested', []))}"
    )
    st.markdown("#### Question")
    st.info(q["question"])

    if q.get("hints"):
        with st.expander("Hints"):
            for i, h in enumerate(q["hints"], 1):
                st.markdown(f"**{i}.** {h}")

    answer   = st.text_area("Your Answer", height=200, placeholder="Type your answer...", key="answer_input")
    c1, c2   = st.columns(2)
    with c1:
        eval_btn = st.button("Evaluate", type="primary", use_container_width=True)
    with c2:
        skip_btn = st.button("Skip / Next", use_container_width=True)

    if skip_btn:
        with st.spinner("Generating..."):
            ctx = get_context_for_generation(driver, company, role, experience, actual)
            nq  = generate_question(company, role, experience, actual, ctx)
            st.session_state.update(current_question=nq, kg_context=ctx, feedback=None, reasoning=None)
            st.rerun()

    if eval_btn:
        if not answer.strip():
            st.warning("Enter an answer first.")
            return
        with st.spinner("Evaluating..."):
            ctx = st.session_state.get("kg_context", {})
            fb  = evaluate_answer(company, q["question"], answer, ctx, q.get("round", actual), experience, role)
            st.session_state.feedback = fb
            ri  = next((r for r in rounds if r["name"] == q.get("round", actual)), {"name": actual, "round_order": 1})
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
    st.markdown("### Evaluation Results")
    score = fb["score"]
    sc    = "score-high" if score >= 8 else "score-mid" if score >= 5 else "score-low"

    sc_col, det_col = st.columns([1, 3])
    with sc_col:
        st.markdown(f'<div class="{sc}">{score}/10</div>', unsafe_allow_html=True)
        st.progress(score / 10)
    with det_col:
        st.markdown("**Strengths**")
        for s in fb.get("strengths", []):
            st.markdown(f"- {s}")

    st.markdown("**Areas for Improvement**")
    for g in fb.get("gaps", []):
        st.markdown(f"- {g}")

    with st.expander("Model Answer"):
        st.markdown(fb.get("ideal_answer", ""))

    if fb.get("skills_to_improve"):
        st.markdown("**Skills to Improve:**")
        for sk in fb["skills_to_improve"]:
            st.markdown(f'<span class="skill-badge badge-critical">{sk}</span>', unsafe_allow_html=True)

    st.markdown("**Next Steps:**")
    for ns in fb.get("next_steps", []):
        st.markdown(f"- {ns}")

    if fb.get("recommended_resources"):
        with st.expander("Resources"):
            for r in fb["recommended_resources"]:
                st.markdown(f"- {r}")

    if st.session_state.reasoning:
        st.markdown("---")
        st.markdown("### Why This Question?")
        st.markdown(f"**KG Path:** {company} → {q.get('round', actual)} → {', '.join(q.get('skills_tested', []))}")
        st.markdown(st.session_state.reasoning)


# ── KG Chat ───────────────────────────────────────────────────────────────────

def _kg_chat(driver, company, role):
    st.markdown('<div class="main-header">KG Chat</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Ask anything about interviews — every answer is traced back to the Knowledge Graph</div>',
        unsafe_allow_html=True,
    )

    # Suggested questions
    st.markdown("**Try asking:**")
    suggestions = [
        f"What rounds does {company} have for {role}?",
        f"What skills are critical for {role} at {company}?",
        f"Show me sample Kafka questions for Netflix Data Engineer",
        f"Compare Netflix and Amazon for Data Engineer",
        f"How do I prepare for the System Design round at Amazon?",
    ]
    cols = st.columns(len(suggestions))
    for i, sug in enumerate(suggestions):
        with cols[i]:
            if st.button(sug, key=f"sug_{i}", use_container_width=True):
                st.session_state.chat_input_value = sug

    st.markdown("---")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-user"><strong>You:</strong> {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="chat-bot"><strong>Prismiq:</strong> {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
            # Show KG sources and runnable Cypher
            if msg.get("kg_results"):
                with st.expander(
                    f"KG Sources — {len(msg['kg_results'])} quer{'y' if len(msg['kg_results']) == 1 else 'ies'} ran"
                ):
                    for result in msg["kg_results"]:
                        st.markdown(
                            f'<span class="kg-badge">KG</span> '
                            f'<strong>{result["description"]}</strong> — '
                            f'{result["row_count"]} rows returned',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Runnable Cypher** — paste directly into Neo4j Browser:")
                        st.markdown(
                            f'<div class="cypher-box">{result["cypher"]}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("---")

    # Input
    prefill = st.session_state.pop("chat_input_value", "")
    user_input = st.chat_input("Ask about any company, role, round, or skill...")

    # Handle suggestion button click
    if prefill and not user_input:
        user_input = prefill

    if user_input:
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Querying Knowledge Graph..."):
            # Get companies and roles from KG for entity extraction
            all_companies = get_companies(driver)
            all_roles     = get_roles(driver)

            # Route query to KG — get exact Cypher + data
            kg_results = route_query(
                driver       = driver,
                query        = user_input,
                companies    = all_companies,
                roles        = all_roles,
                default_company = company,
                default_role    = role,
            )

            # Generate answer from KG data
            answer = answer_from_kg(user_input, kg_results)

            # Build serializable result summaries for display
            result_summaries = [
                {
                    "description": r.description,
                    "row_count":   len(r.data),
                    "cypher":      r.runnable_cypher,
                }
                for r in kg_results
            ]

        # Add bot message with KG sources
        st.session_state.chat_history.append({
            "role":       "assistant",
            "content":    answer,
            "kg_results": result_summaries,
        })

        st.rerun()

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("Clear chat", use_container_width=False):
            st.session_state.chat_history = []
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(_CSS, unsafe_allow_html=True)
    driver = _init_driver()

    if driver is None:
        st.error("Cannot connect to Neo4j. Check that Neo4j is running and `.env` has correct credentials.")
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