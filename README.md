# Prismiq — AI-Powered Interview Preparation Platform

Prismiq combines **Knowledge Graphs (Neo4j)** and **LLMs (GPT-4o-mini)** via a **Retrieval-Augmented Generation (RAG)** architecture to deliver personalized, company-specific interview preparation for **Data Scientist**, **Data Engineer**, and **Data Analyst** roles at 9 top tech companies.

> **Course:** DAMG 7374 — LLM with Knowledge Graph DB (SEC 02), Spring 2026  
> **Team:** Nidhi Nair · Riyanshi Kedia · Tirth Patel  
> **Institution:** Northeastern University, College of Engineering

---

## Supported Companies & Roles

| Company    | Data Scientist | Data Engineer | Data Analyst |
|------------|:-:|:-:|:-:|
| Google     | ✓ | ✓ | ✓ |
| Amazon     | ✓ | ✓ | ✓ |
| Meta       | ✓ | ✓ | ✓ |
| Apple      | ✓ | ✓ | ✓ |
| Netflix    | ✓ | ✓ | ✓ |
| Microsoft  | ✓ | ✓ | ✓ |
| Tesla      | ✓ | ✓ | ✓ |
| TikTok     | ✓ | ✓ | ✓ |
| Uber       | ✓ | ✓ | ✓ |

**3 experience levels:** Entry · Mid · Senior  
**6 interview rounds per company-role pair** (filtered by experience level)

---

## How It Works

```
User selects Company + Role + Experience Level
        ↓
Knowledge Graph (Neo4j) retrieves relevant rounds, skills, and questions
        ↓
LLM (GPT-4o-mini) generates a targeted question using KG context (RAG)
        ↓
User answers → LLM evaluates with role-specific scoring rubrics
        ↓
KG reasoning path explains WHY this question was asked
```

---

## Features

- **Dashboard** — Company/role overview: interview rounds (filtered by level), required skills (Must Have / Good to Have), quick stats
- **Practice Mode** — Generate question → answer → get scored (1–10) with strengths, gaps, model answer, skills to improve, next steps, and recommended resources
- **KG Chat** — Natural language queries against the Knowledge Graph with runnable Cypher shown for every answer

---

## Knowledge Graph Stats

| Metric | Value |
|--------|-------|
| Total Nodes | 748 |
| Total Relationships | 3,030 |
| Companies | 9 |
| Roles | 3 |
| Experience Levels | 3 |
| Interview Rounds | 162 (6 per company-role pair) |
| Interview Questions | 450 (50 per company) |
| Skills | 76 |
| Learning Resources | 45 |

**Zero GPT-generated content in the KG** — all data sourced from real platforms.

---

## Data Sources

| Source | What It Provides | Details |
|--------|-----------------|---------|
| LeetCode (GitHub) | Company-tagged coding problems | [krishnadey30/LeetCode-Questions-CompanyWise](https://github.com/krishnadey30/LeetCode-Questions-CompanyWise) — filtered by difficulty + SQL keywords for DA |
| Glassdoor / Blind / Levels.fyi | Interview round structures | 27 structures (9 companies × 3 roles), manually verified and hardcoded in `llm/seeds.py` |
| Kaggle Job Postings | Skill extraction | [asaniczka/data-science-job-postings-and-skills](https://www.kaggle.com/datasets/asaniczka/data-science-job-postings-and-skills) — frequency-based importance scoring |
| Curated GitHub Repos | DS/DE interview questions | Supplementary questions for companies without LeetCode CSVs |
| Manual Curation | Learning resources | 45 resources with real URLs mapped to specific skills |

---

## Project Structure

```
Prismiq/
├── config.py                  ← Central config: roles, companies, mappings, UI constants
├── models.py                  ← Pydantic models for validation + custom exceptions
├── data/
│   ├── kaggle_extract.py      ← LeetCode extraction from GitHub + Kaggle skill extraction
│   ├── github_extract.py      ← Questions from curated GitHub repos
│   ├── job_market_extract.py  ← Skills from Kaggle job postings
│   └── resources.py           ← 45 curated learning resources with real URLs
├── kg/
│   ├── schema.py              ← Neo4j constraints (7), indexes (5), driver lifecycle
│   ├── load_kg.py             ← Loads all extracted data into Neo4j with relationships
│   ├── kg_retrieval.py        ← Parameterized Cypher queries for RAG context assembly
│   └── kg_chat.py             ← Routes NL queries to Cypher templates for KG Chat
├── llm/
│   ├── seeds.py               ← Hardcoded interview round structures (all roles × companies)
│   ├── generator.py           ← Role-aware question generation grounded by KG context
│   ├── evaluator.py           ← Role-aware answer evaluation with scoring rubrics
│   ├── chat.py                ← LLM chat integration for KG Chat answers
│   └── round_filter.py        ← Filters interview rounds by experience level
├── app/
│   └── app.py                 ← Streamlit UI: Dashboard, Practice Mode, KG Chat
├── tests/
│   └── test_config.py         ← Configuration tests
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.9+
- Neo4j Desktop (or AuraDB)
- OpenAI API key

### Installation

```bash
git clone https://github.com/riyanshikedia10/Prismiq.git
cd Prismiq
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your keys to `.env`:

```
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
KAGGLE_USERNAME=your-username    # optional
KAGGLE_KEY=your-key              # optional
```

### Running

Start Neo4j Desktop → run your instance → then:

```bash
# Step 1: Extract data
python data/kaggle_extract.py        # LeetCode problems + Kaggle skills
python data/github_extract.py        # GitHub repo questions
python data/job_market_extract.py    # Kaggle job posting skills

# Step 2: Load into Neo4j
python kg/load_kg.py

# Step 3: Launch
streamlit run app/app.py
```

---

## Tech Stack

Neo4j · Cypher · OpenAI GPT-4o-mini · Streamlit · Python 3.9+ · Pydantic · Tenacity

---

## Related Work

This project builds on the **HRGraph** framework (Wasi, 2024) — presented as our midterm deliverable — which demonstrated that LLM-constructed Knowledge Graphs can effectively serve HR tasks like job matching and classification. Prismiq extends this paradigm by using the KG as a **retrieval source for RAG** rather than just an LLM output, with all KG content sourced from real data to mitigate the hallucination risks HRGraph identified.

> Wasi, A.T. (2024). *HRGraph: Leveraging LLMs for HR Data Knowledge Graphs with Information Propagation-based Job Recommendation.* arXiv:2408.13521.# Prismiq — AI-Powered Interview Preparation Platform

Prismiq combines **Knowledge Graphs (Neo4j)** and **LLMs (GPT-4o-mini)** via a **Retrieval-Augmented Generation (RAG)** architecture to deliver personalized, company-specific interview preparation for **Data Scientist**, **Data Engineer**, and **Data Analyst** roles at 9 top tech companies.

> **Course:** DAMG 7374 — LLM with Knowledge Graph DB (SEC 02), Spring 2026  
> **Team:** Nidhi Nair · Riyanshi Kedia · Tirth Patel  
> **Institution:** Northeastern University, College of Engineering

---

## Supported Companies & Roles

| Company    | Data Scientist | Data Engineer | Data Analyst |
|------------|:-:|:-:|:-:|
| Google     | ✓ | ✓ | ✓ |
| Amazon     | ✓ | ✓ | ✓ |
| Meta       | ✓ | ✓ | ✓ |
| Apple      | ✓ | ✓ | ✓ |
| Netflix    | ✓ | ✓ | ✓ |
| Microsoft  | ✓ | ✓ | ✓ |
| Tesla      | ✓ | ✓ | ✓ |
| TikTok     | ✓ | ✓ | ✓ |
| Uber       | ✓ | ✓ | ✓ |

**3 experience levels:** Entry · Mid · Senior  
**6 interview rounds per company-role pair** (filtered by experience level)

---

## How It Works

```
User selects Company + Role + Experience Level
        ↓
Knowledge Graph (Neo4j) retrieves relevant rounds, skills, and questions
        ↓
LLM (GPT-4o-mini) generates a targeted question using KG context (RAG)
        ↓
User answers → LLM evaluates with role-specific scoring rubrics
        ↓
KG reasoning path explains WHY this question was asked
```

---

## Features

- **Dashboard** — Company/role overview: interview rounds (filtered by level), required skills (Must Have / Good to Have), quick stats
- **Practice Mode** — Generate question → answer → get scored (1–10) with strengths, gaps, model answer, skills to improve, next steps, and recommended resources
- **KG Chat** — Natural language queries against the Knowledge Graph with runnable Cypher shown for every answer

---

## Knowledge Graph Stats

| Metric | Value |
|--------|-------|
| Total Nodes | 748 |
| Total Relationships | 3,030 |
| Companies | 9 |
| Roles | 3 |
| Experience Levels | 3 |
| Interview Rounds | 162 (6 per company-role pair) |
| Interview Questions | 450 (50 per company) |
| Skills | 76 |
| Learning Resources | 45 |

**Zero GPT-generated content in the KG** — all data sourced from real platforms.

---

## Data Sources

| Source | What It Provides | Details |
|--------|-----------------|---------|
| LeetCode (GitHub) | Company-tagged coding problems | [krishnadey30/LeetCode-Questions-CompanyWise](https://github.com/krishnadey30/LeetCode-Questions-CompanyWise) — filtered by difficulty + SQL keywords for DA |
| Glassdoor / Blind / Levels.fyi | Interview round structures | 27 structures (9 companies × 3 roles), manually verified and hardcoded in `llm/seeds.py` |
| Kaggle Job Postings | Skill extraction | [asaniczka/data-science-job-postings-and-skills](https://www.kaggle.com/datasets/asaniczka/data-science-job-postings-and-skills) — frequency-based importance scoring |
| Curated GitHub Repos | DS/DE interview questions | Supplementary questions for companies without LeetCode CSVs |
| Manual Curation | Learning resources | 45 resources with real URLs mapped to specific skills |

---

## Project Structure

```
Prismiq/
├── config.py                  ← Central config: roles, companies, mappings, UI constants
├── models.py                  ← Pydantic models for validation + custom exceptions
├── data/
│   ├── kaggle_extract.py      ← LeetCode extraction from GitHub + Kaggle skill extraction
│   ├── github_extract.py      ← Questions from curated GitHub repos
│   ├── job_market_extract.py  ← Skills from Kaggle job postings
│   └── resources.py           ← 45 curated learning resources with real URLs
├── kg/
│   ├── schema.py              ← Neo4j constraints (7), indexes (5), driver lifecycle
│   ├── load_kg.py             ← Loads all extracted data into Neo4j with relationships
│   ├── kg_retrieval.py        ← Parameterized Cypher queries for RAG context assembly
│   └── kg_chat.py             ← Routes NL queries to Cypher templates for KG Chat
├── llm/
│   ├── seeds.py               ← Hardcoded interview round structures (all roles × companies)
│   ├── generator.py           ← Role-aware question generation grounded by KG context
│   ├── evaluator.py           ← Role-aware answer evaluation with scoring rubrics
│   ├── chat.py                ← LLM chat integration for KG Chat answers
│   └── round_filter.py        ← Filters interview rounds by experience level
├── app/
│   └── app.py                 ← Streamlit UI: Dashboard, Practice Mode, KG Chat
├── tests/
│   └── test_config.py         ← Configuration tests
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.9+
- Neo4j Desktop (or AuraDB)
- OpenAI API key

### Installation

```bash
git clone https://github.com/riyanshikedia10/Prismiq.git
cd Prismiq
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your keys to `.env`:

```
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
KAGGLE_USERNAME=your-username    # optional
KAGGLE_KEY=your-key              # optional
```

### Running

Start Neo4j Desktop → run your instance → then:

```bash
# Step 1: Extract data
python data/kaggle_extract.py        # LeetCode problems + Kaggle skills
python data/github_extract.py        # GitHub repo questions
python data/job_market_extract.py    # Kaggle job posting skills

# Step 2: Load into Neo4j
python kg/load_kg.py

# Step 3: Launch
streamlit run app/app.py
```

---

## Tech Stack

Neo4j · Cypher · OpenAI GPT-4o-mini · Streamlit · Python 3.9+ · Pydantic · Tenacity

---

## Related Work

This project builds on the **HRGraph** framework (Wasi, 2024) — presented as our midterm deliverable — which demonstrated that LLM-constructed Knowledge Graphs can effectively serve HR tasks like job matching and classification. Prismiq extends this paradigm by using the KG as a **retrieval source for RAG** rather than just an LLM output, with all KG content sourced from real data to mitigate the hallucination risks HRGraph identified.

> Wasi, A.T. (2024). *HRGraph: Leveraging LLMs for HR Data Knowledge Graphs with Information Propagation-based Job Recommendation.* arXiv:2408.13521.
