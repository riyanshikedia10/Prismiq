# Prismiq — AI-Powered Interview Preparation Platform

Prismiq combines **Knowledge Graphs** and **LLMs** to deliver personalized, company-specific interview preparation for **Data Scientist**, **Data Engineer**, and **Data Analyst** roles at 9 top tech companies.

---

## Supported Companies & Roles

| Company    | Data Scientist | Data Engineer | Data Analyst |
|------------|:-:|:-:|:-:|
| Google     | ✅ | ✅ | ✅ |
| Amazon     | ✅ | ✅ | ✅ |
| Meta       | ✅ | ✅ | ✅ |
| Apple      | ✅ | ✅ | ✅ |
| Netflix    | ✅ | ✅ | ✅ |
| Microsoft  | ✅ | ✅ | ✅ |
| Tesla      | ✅ | ✅ | ✅ |
| TikTok     | ✅ | ✅ | ✅ |
| Uber       | ✅ | ✅ | ✅ |

---

## How It Works

```
User selects Company + Role + Experience Level
        ↓
Knowledge Graph (Neo4j) retrieves relevant skills + questions for that role
        ↓
LLM (GPT-4o-mini) generates a targeted question using KG context
        ↓
User answers → LLM evaluates and gives structured feedback
        ↓
KG reasoning path explains WHY this question was asked
```

---

## Data Sources

| Approach | Source | What it provides |
|----------|--------|-----------------|
| **A** — GPT Extraction | GPT-4o-mini + verified seed structures | Skills, sample questions, learning resources per (role, company) |
| **B** — Real Datasets | LeetCode (GitHub) + Kaggle job postings | Company-tagged coding problems + verified skill frequencies |
| **C** — Raw Files | Job descriptions, Glassdoor, GitHub repos | DE-specific skills from JDs, interview questions from community |

---

## Project Structure

```
Prismiq/
├── config.py               ← Central configuration (roles, companies, mappings)
├── data/
│   ├── kaggle_extract.py   ← Approach B: LeetCode + Kaggle (all roles)
│   ├── raw/                ← JDs, Glassdoor text, GitHub markdown
│   └── processed/          ← Output JSON files
├── kg/
│   ├── schema.py           ← Neo4j constraints, indexes, driver
│   ├── load_kg.py          ← Unified loader (Approach A + B + C)
│   └── kg_retrieval.py     ← Role-aware Cypher queries + RAG context
├── llm/
│   ├── seeds.py            ← Interview round structures (all roles × companies)
│   ├── extract.py          ← Approach A: GPT extraction (all roles)
│   ├── extract_raw.py      ← Approach C: JD/Glassdoor/GitHub extraction
│   ├── generator.py        ← Role-aware question generation
│   └── evaluator.py        ← Role-aware answer evaluation
├── app/
│   └── app.py              ← Streamlit UI (multi-role)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

```bash
git clone https://github.com/riyanshikedia10/Prismiq.git
cd Prismiq
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your API keys
```

Start Neo4j Desktop → run your instance → then:

```bash
# Step 1: Extract data (pick what you need)
python llm/extract.py                       # Approach A — all roles
python llm/extract.py --role "Data Engineer" # Approach A — single role
python data/kaggle_extract.py               # Approach B — LeetCode + Kaggle
python llm/extract_raw.py                   # Approach C — JDs/Glassdoor (DE)

# Step 2: Load into Neo4j
python kg/load_kg.py

# Step 3: Launch the app
streamlit run app/app.py
```

---

## Tech Stack

Neo4j · Cypher · OpenAI GPT-4o-mini · Streamlit · Python 3.9+

## Team — 6

Nidhi Nair · Riyanshi Kedia · Tirth Patel
INFO 7260 — Northeastern University, Spring 2026
