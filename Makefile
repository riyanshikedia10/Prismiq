.PHONY: install extract load run lint test clean

install:
	pip install -r requirements.txt

# ── Data extraction (all real sources, zero GPT) ─────────────
extract-leetcode:
	python data/kaggle_extract.py

extract-github:
	python data/github_extract.py

extract-jobmarket:
	python data/job_market_extract.py

extract: extract-leetcode extract-github extract-jobmarket

# ── Knowledge Graph ──────────────────────────────────────────
load:
	python kg/load_kg.py

schema:
	python kg/schema.py

# ── Application ──────────────────────────────────────────────
run:
	streamlit run app/app.py

# ── Quality ──────────────────────────────────────────────────
lint:
	ruff check .

format:
	ruff format .

test:
	pytest tests/ -v

# ── Full pipeline ────────────────────────────────────────────
all: extract load run

# ── Cleanup ──────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
