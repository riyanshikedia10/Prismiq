# Prismiq — AI-Powered Interview Preparation Platform

Prismiq combines **Knowledge Graphs** and **LLMs** to deliver personalized, company-specific interview preparation for Data Engineer, Data Scientist and Data Analyst roles.

---

## How It Works

```
User selects Company + Role + Experience
        ↓
Knowledge Graph (Neo4j) retrieves relevant skills + questions
        ↓
LLM (GPT-4o-mini) generates a targeted question using KG context
        ↓
User answers → LLM evaluates and gives structured feedback
```

---

## Project Structure

```
Prismiq/
├── data/
│   ├── raw/               ← copy-pasted JDs and Glassdoor text
│   └── processed/         ← extracted JSON files
├── kg/
│   ├── load_kg.py         ← loads data into Neo4j
│   └── kg_retrieval.py    ← query functions
├── llm/
│   ├── extract.py         ← extracts skills/questions using GPT
│   ├── generator.py       ← generates interview questions
│   └── evaluator.py       ← evaluates user answers
├── app/
│   └── app.py             ← Streamlit UI
├── .env.example
└── requirements.txt
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
python llm/extract.py       # extract data
python kg/load_kg.py        # load into Neo4j
streamlit run app/app.py    # launch app
```

---

## Tech Stack
Neo4j · Cypher · OpenAI GPT-4o-mini · Streamlit · Python 3.9+

## Team - 6
Nidhi Nair · Riyanshi Kedia · Tirth Patel
INFO 7260 — Northeastern University, Spring 2026
