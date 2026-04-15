"""
Extract real interview questions from curated GitHub repositories.
Parses markdown files and outputs structured JSON — zero GPT involvement.

Sources:
  1. alexeygrigorev/data-science-interviews (9.8k stars) — DS theory + technical
  2. youssefHosni/Data-Science-Interview-Questions-Answers (5.6k stars) — DS categorized Q&A
  3. OBenner/data-engineering-interview-questions — DE topic-wise questions

Outputs:
  data/processed/github_ds_questions.json
  data/processed/github_de_questions.json
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from config import setup_logging

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
OUT_DIR = Path(__file__).parent / "processed"

# ── Markdown parsers ─────────────────────────────────────────────────────────

def _extract_questions_bold_pattern(text: str) -> list[str]:
    """Extract questions formatted as **Question text? emoji**"""
    return [
        m.group(1).strip().rstrip("👶⭐️🚀 ‍")
        for m in re.finditer(r"\*\*(.+?\?)\s*[👶⭐️🚀‍ ]*\*\*", text)
        if len(m.group(1).strip()) > 15
    ]


def _extract_questions_heading_pattern(text: str) -> list[str]:
    """Extract questions from ### Q1: ... ### headings"""
    return [
        m.group(1).strip()
        for m in re.finditer(r"###\s*Q\d+:\s*(.+?)(?:\s*###|\s*$)", text, re.MULTILINE)
        if len(m.group(1).strip()) > 15
    ]


def _extract_questions_link_toc(text: str) -> list[str]:
    """Extract questions from + [Question text](#anchor) table-of-contents"""
    return [
        m.group(1).strip().rstrip("?") + "?"
        for m in re.finditer(r"\+\s*\[(.+?\??)\]", text)
        if len(m.group(1).strip()) > 15 and "main title" not in m.group(1).lower()
    ]


def _difficulty_from_emoji(text: str) -> str:
    if "👶" in text:
        return "Easy"
    if "🚀" in text:
        return "Hard"
    return "Medium"


# ── Repo 1: alexeygrigorev/data-science-interviews ──────────────────────────

def _parse_alexey_theory(filepath: Path) -> list[dict]:
    """Parse theory.md — questions in **bold?** with emoji difficulty markers."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    questions = []

    current_section = "General"
    for line in text.split("\n"):
        section_match = re.match(r"^##\s+(.+)", line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        q_match = re.match(r"\*\*(.+?\?)\s*([👶⭐️🚀‍ ]*)\*\*", line)
        if q_match and len(q_match.group(1).strip()) > 15:
            questions.append({
                "text": q_match.group(1).strip(),
                "topic": current_section,
                "difficulty": _difficulty_from_emoji(q_match.group(2)),
                "source": "github:alexeygrigorev/data-science-interviews",
                "role": "Data Scientist",
            })

    return questions


def _parse_alexey_technical(filepath: Path) -> list[dict]:
    """Parse technical.md — SQL/Python coding questions."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    questions = []

    current_section = "General"
    for line in text.split("\n"):
        section_match = re.match(r"^##\s+(.+)", line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        q_match = re.match(r"\*\*(.+?\?)\s*([👶⭐️🚀‍ ]*)\*\*", line)
        if q_match and len(q_match.group(1).strip()) > 15:
            questions.append({
                "text": q_match.group(1).strip(),
                "topic": current_section,
                "difficulty": _difficulty_from_emoji(q_match.group(2)),
                "source": "github:alexeygrigorev/data-science-interviews",
                "role": "Data Scientist",
            })

    return questions


# ── Repo 2: youssefHosni DS Q&A ─────────────────────────────────────────────

_YOUSSEF_FILE_MAP = {
    "Machine Learning Interview Questions & Answers for Data Scientists.md": "Machine Learning",
    "Deep Learning Questions & Answers for Data Scientists.md": "Deep Learning",
    "Probability Interview Questions & Answers for Data Scientists.md": "Probability",
    "Statistics Interview Questions & Answers for Data Scientists.md": "Statistics",
    "Python Interview Questions & Answers for Data Scientists.md": "Python",
    "SQL & DB Interview Questions & Answers for Data Scientists.md": "SQL",
}


def _parse_youssef_file(filepath: Path, topic: str) -> list[dict]:
    """Parse youssefHosni Q&A files — Q1-QN heading pattern."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    questions = []

    for m in re.finditer(r"###\s*Q\d+:\s*(.+?)(?:\s*###|\s*\.?\s*$)", text, re.MULTILINE):
        q_text = m.group(1).strip().rstrip("#").strip()
        if len(q_text) > 15:
            questions.append({
                "text": q_text if q_text.endswith("?") else q_text + "?",
                "topic": topic,
                "difficulty": "Medium",
                "source": "github:youssefHosni/Data-Science-Interview-Questions-Answers",
                "role": "Data Scientist",
            })

    return questions


# ── Repo 3: OBenner DE interview questions ───────────────────────────────────

_DE_TOPIC_MAP = {
    "spark.md": "Apache Spark", "kafka.md": "Kafka", "airflow.md": "Airflow",
    "sql.md": "SQL", "python.md": "Python", "flink.md": "Apache Flink",
    "data-modeling.md": "Data Modeling", "system-design.md": "System Design",
    "cdc.md": "CDC", "iceberg.md": "Apache Iceberg", "hive.md": "Hive",
    "hadoop.md": "Hadoop", "cassandra.md": "Cassandra", "redshift.md": "Redshift",
    "aws.md": "AWS", "gcp.md": "GCP", "azure.md": "Azure",
    "docker.md": "Docker", "kubernetes.md": "Kubernetes",
    "data-quality.md": "Data Quality", "data-governance.md": "Data Governance",
    "dbt.md": "dbt", "delta.md": "Delta Lake", "hudi.md": "Apache Hudi",
    "parquet.md": "Parquet", "avro.md": "Avro",
    "bigquery.md": "BigQuery", "dynamodb.md": "DynamoDB",
    "mongo.md": "MongoDB", "nifi.md": "Apache NiFi",
    "observability.md": "Observability", "tableau.md": "Tableau",
    "looker.md": "Looker", "superset.md": "Superset",
    "dwha.md": "Data Warehousing", "cost-optimization.md": "Cost Optimization",
    "hbase.md": "HBase", "impala.md": "Impala", "flume.md": "Flume",
    "greenplum.md": "Greenplum", "bigtable.md": "Bigtable",
    "data-structure.md": "Data Structures",
}


def _parse_obenner_file(filepath: Path, topic: str) -> list[dict]:
    """Parse OBenner DE files — + [Question](#anchor) TOC pattern."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    questions = []

    for m in re.finditer(r"\+\s*\[(.+?)\]\(#", text):
        q_text = m.group(1).strip()
        if len(q_text) > 15 and "main title" not in q_text.lower() and "interview questions" not in q_text.lower():
            questions.append({
                "text": q_text if q_text.endswith("?") else q_text + "?",
                "topic": topic,
                "difficulty": "Medium",
                "source": "github:OBenner/data-engineering-interview-questions",
                "role": "Data Engineer",
            })

    return questions


# ── Skill mapping ────────────────────────────────────────────────────────────

_TOPIC_TO_SKILLS: dict[str, list[str]] = {
    "Supervised machine learning": ["Machine Learning", "Statistics"],
    "Linear regression": ["Machine Learning", "Statistics"],
    "Validation": ["Machine Learning"],
    "Classification": ["Machine Learning"],
    "Regularization": ["Machine Learning"],
    "Feature selection": ["Machine Learning"],
    "Decision trees": ["Machine Learning"],
    "Random forest": ["Machine Learning"],
    "Gradient boosting": ["Machine Learning"],
    "Parameter tuning": ["Machine Learning"],
    "Neural networks": ["Deep Learning"],
    "Optimization in neural networks": ["Deep Learning"],
    "Neural networks for computer vision": ["Deep Learning"],
    "Text classification": ["Machine Learning", "NLP"],
    "Clustering": ["Machine Learning"],
    "Dimensionality reduction": ["Machine Learning"],
    "Ranking and search": ["Machine Learning"],
    "Recommender systems": ["Machine Learning"],
    "Time series": ["Statistics", "Machine Learning"],
    "Machine Learning": ["Machine Learning"],
    "Deep Learning": ["Deep Learning"],
    "Probability": ["Probability", "Statistics"],
    "Statistics": ["Statistics"],
    "Python": ["Python"],
    "SQL": ["SQL"],
    "Apache Spark": ["Apache Spark"],
    "Kafka": ["Kafka"],
    "Airflow": ["Airflow"],
    "Data Modeling": ["Data Modeling"],
    "System Design": ["System Design"],
    "CDC": ["CDC"],
    "Apache Iceberg": ["Apache Iceberg"],
    "Apache Flink": ["Apache Flink"],
    "AWS": ["AWS"], "GCP": ["GCP"], "Azure": ["Azure"],
    "Docker": ["Docker"], "Kubernetes": ["Kubernetes"],
    "Data Quality": ["Data Quality"], "Data Governance": ["Data Governance"],
    "dbt": ["dbt"], "Delta Lake": ["Delta Lake"],
    "Data Warehousing": ["Data Warehousing"],
    "Hive": ["Hive"], "Hadoop": ["Hadoop"],
    "Redshift": ["Redshift"], "BigQuery": ["BigQuery"],
    "Cassandra": ["Cassandra"], "DynamoDB": ["DynamoDB"],
    "MongoDB": ["MongoDB"], "Parquet": ["Parquet"],
}

_TOPIC_TO_ROUND: dict[str, str] = {
    "SQL": "Technical Screen",
    "Python": "Technical Screen",
    "Machine Learning": "Onsite: Stats & ML",
    "Deep Learning": "Onsite: Stats & ML",
    "Statistics": "Onsite: Stats & ML",
    "Probability": "Onsite: Stats & ML",
    "Apache Spark": "Onsite: Coding",
    "Kafka": "Onsite: System Design",
    "Airflow": "Onsite: System Design",
    "Data Modeling": "Onsite: Data Modeling",
    "System Design": "Onsite: System Design",
    "AWS": "Onsite: System Design",
    "GCP": "Onsite: System Design",
    "Azure": "Onsite: System Design",
    "Docker": "Onsite: Coding",
    "Kubernetes": "Onsite: System Design",
    "Data Warehousing": "Onsite: Data Modeling",
}


def _enrich_question(q: dict) -> dict:
    """Add skills_tested and round based on topic."""
    topic = q["topic"]
    q["skills_tested"] = _TOPIC_TO_SKILLS.get(topic, [topic])
    q["round"] = _TOPIC_TO_ROUND.get(topic, "Technical Screen")
    q["experience_levels"] = ["Entry", "Mid", "Senior"]
    return q


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ds_questions: list[dict] = []
    de_questions: list[dict] = []

    # Repo 1: alexeygrigorev
    repo1 = RAW_DIR / "ds-interviews"
    if repo1.exists():
        theory = repo1 / "theory.md"
        technical = repo1 / "technical.md"
        if theory.exists():
            qs = _parse_alexey_theory(theory)
            ds_questions.extend(qs)
            logger.info("[alexeygrigorev/theory.md] %d questions", len(qs))
        if technical.exists():
            qs = _parse_alexey_technical(technical)
            ds_questions.extend(qs)
            logger.info("[alexeygrigorev/technical.md] %d questions", len(qs))
    else:
        logger.warning("Repo ds-interviews not cloned at %s", repo1)

    # Repo 2: youssefHosni
    repo2 = RAW_DIR / "ds-qa"
    if repo2.exists():
        for filename, topic in _YOUSSEF_FILE_MAP.items():
            fp = repo2 / filename
            if fp.exists():
                qs = _parse_youssef_file(fp, topic)
                ds_questions.extend(qs)
                logger.info("[youssefHosni/%s] %d questions", topic, len(qs))
    else:
        logger.warning("Repo ds-qa not cloned at %s", repo2)

    # Repo 3: OBenner
    repo3 = RAW_DIR / "de-interviews"
    content_dir = repo3 / "content"
    if content_dir.exists():
        for filename, topic in _DE_TOPIC_MAP.items():
            fp = content_dir / filename
            if fp.exists():
                qs = _parse_obenner_file(fp, topic)
                de_questions.extend(qs)
                logger.info("[OBenner/%s] %d questions", topic, len(qs))
    else:
        logger.warning("Repo de-interviews not cloned at %s", repo3)

    # Enrich with skills and rounds
    ds_questions = [_enrich_question(q) for q in ds_questions]
    de_questions = [_enrich_question(q) for q in de_questions]

    # Deduplicate by question text
    def _dedup(qs: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out = []
        for q in qs:
            key = q["text"].lower().strip().rstrip("?")
            if key not in seen:
                seen.add(key)
                out.append(q)
        return out

    ds_questions = _dedup(ds_questions)
    de_questions = _dedup(de_questions)

    # Save
    ds_path = OUT_DIR / "github_ds_questions.json"
    with open(ds_path, "w") as f:
        json.dump(ds_questions, f, indent=2)
    logger.info("DS: %d questions -> %s", len(ds_questions), ds_path)

    de_path = OUT_DIR / "github_de_questions.json"
    with open(de_path, "w") as f:
        json.dump(de_questions, f, indent=2)
    logger.info("DE: %d questions -> %s", len(de_questions), de_path)


if __name__ == "__main__":
    setup_logging()
    run()
