"""
Curated learning resources — real URLs, manually verified.
No GPT involvement. Each resource is mapped to one or more skills.
"""

RESOURCES: list[dict] = [
    # ── SQL ───────────────────────────────────────────────────────────────────
    {"name": "DataLemur SQL Questions", "url": "https://datalemur.com/questions", "skill": "SQL", "type": "Tool"},
    {"name": "Mode Analytics SQL Tutorial", "url": "https://mode.com/sql-tutorial/", "skill": "SQL", "type": "Course"},
    {"name": "W3Schools SQL Tutorial", "url": "https://www.w3schools.com/sql/", "skill": "SQL", "type": "Course"},
    {"name": "LeetCode Database Problems", "url": "https://leetcode.com/problemset/database/", "skill": "SQL", "type": "Tool"},
    {"name": "SQLZoo Interactive Tutorial", "url": "https://sqlzoo.net/", "skill": "SQL", "type": "Course"},
    {"name": "StrataScratch SQL Questions", "url": "https://www.stratascratch.com/", "skill": "SQL", "type": "Tool"},

    # ── Python ────────────────────────────────────────────────────────────────
    {"name": "LeetCode Python Problems", "url": "https://leetcode.com/problemset/all/", "skill": "Python", "type": "Tool"},
    {"name": "Real Python Tutorials", "url": "https://realpython.com/", "skill": "Python", "type": "Article"},
    {"name": "Python Official Docs", "url": "https://docs.python.org/3/tutorial/", "skill": "Python", "type": "Article"},
    {"name": "HackerRank Python Practice", "url": "https://www.hackerrank.com/domains/python", "skill": "Python", "type": "Tool"},

    # ── Machine Learning ──────────────────────────────────────────────────────
    {"name": "Andrew Ng — Machine Learning (Coursera)", "url": "https://www.coursera.org/learn/machine-learning", "skill": "Machine Learning", "type": "Course"},
    {"name": "StatQuest ML Videos", "url": "https://www.youtube.com/c/joshstarmer", "skill": "Machine Learning", "type": "Course"},
    {"name": "Hands-On ML with Scikit-Learn (Book)", "url": "https://www.oreilly.com/library/view/hands-on-machine-learning/9781098125967/", "skill": "Machine Learning", "type": "Book"},
    {"name": "Google ML Crash Course", "url": "https://developers.google.com/machine-learning/crash-course", "skill": "Machine Learning", "type": "Course"},
    {"name": "Kaggle Learn — Intro to ML", "url": "https://www.kaggle.com/learn/intro-to-machine-learning", "skill": "Machine Learning", "type": "Course"},

    # ── Statistics & Probability ──────────────────────────────────────────────
    {"name": "StatQuest Statistics", "url": "https://www.youtube.com/c/joshstarmer", "skill": "Statistics", "type": "Course"},
    {"name": "Khan Academy Statistics", "url": "https://www.khanacademy.org/math/statistics-probability", "skill": "Statistics", "type": "Course"},
    {"name": "Seeing Theory (Interactive)", "url": "https://seeing-theory.brown.edu/", "skill": "Probability", "type": "Tool"},
    {"name": "Think Stats (Free Book)", "url": "https://greenteapress.com/thinkstats2/", "skill": "Statistics", "type": "Book"},

    # ── Deep Learning ─────────────────────────────────────────────────────────
    {"name": "Deep Learning Specialization (Coursera)", "url": "https://www.coursera.org/specializations/deep-learning", "skill": "Deep Learning", "type": "Course"},
    {"name": "Fast.ai Practical Deep Learning", "url": "https://course.fast.ai/", "skill": "Deep Learning", "type": "Course"},
    {"name": "Deep Learning Book (Goodfellow)", "url": "https://www.deeplearningbook.org/", "skill": "Deep Learning", "type": "Book"},

    # ── A/B Testing ───────────────────────────────────────────────────────────
    {"name": "Evan Miller A/B Testing Guide", "url": "https://www.evanmiller.org/ab-testing/", "skill": "A/B Testing", "type": "Article"},
    {"name": "Trustworthy Online Experiments (Book)", "url": "https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/", "skill": "A/B Testing", "type": "Book"},

    # ── Apache Spark ──────────────────────────────────────────────────────────
    {"name": "Spark: The Definitive Guide (Book)", "url": "https://www.oreilly.com/library/view/spark-the-definitive/9781491912201/", "skill": "Apache Spark", "type": "Book"},
    {"name": "Spark Official Documentation", "url": "https://spark.apache.org/docs/latest/", "skill": "Apache Spark", "type": "Article"},
    {"name": "Databricks Learning Academy", "url": "https://www.databricks.com/learn", "skill": "Apache Spark", "type": "Course"},

    # ── Kafka ─────────────────────────────────────────────────────────────────
    {"name": "Confluent Kafka Documentation", "url": "https://docs.confluent.io/platform/current/overview.html", "skill": "Kafka", "type": "Article"},
    {"name": "Kafka: The Definitive Guide (Book)", "url": "https://www.confluent.io/resources/kafka-the-definitive-guide-v2/", "skill": "Kafka", "type": "Book"},

    # ── Airflow ───────────────────────────────────────────────────────────────
    {"name": "Apache Airflow Documentation", "url": "https://airflow.apache.org/docs/", "skill": "Airflow", "type": "Article"},
    {"name": "Astronomer Airflow Guides", "url": "https://docs.astronomer.io/learn", "skill": "Airflow", "type": "Course"},

    # ── Data Modeling ─────────────────────────────────────────────────────────
    {"name": "Kimball Dimensional Modeling (Book)", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/", "skill": "Data Modeling", "type": "Book"},

    # ── System Design ─────────────────────────────────────────────────────────
    {"name": "Designing Data-Intensive Applications (Book)", "url": "https://dataintensive.net/", "skill": "System Design", "type": "Book"},
    {"name": "System Design Primer (GitHub)", "url": "https://github.com/donnemartin/system-design-primer", "skill": "System Design", "type": "Article"},

    # ── Cloud (AWS / GCP / Azure) ─────────────────────────────────────────────
    {"name": "AWS Data Analytics Specialty Guide", "url": "https://aws.amazon.com/certification/certified-data-analytics-specialty/", "skill": "AWS", "type": "Course"},
    {"name": "Google Cloud Data Engineer Path", "url": "https://cloud.google.com/learn/certification/data-engineer", "skill": "GCP", "type": "Course"},

    # ── Data Visualization ────────────────────────────────────────────────────
    {"name": "Tableau Public Gallery", "url": "https://public.tableau.com/gallery/", "skill": "Tableau", "type": "Tool"},
    {"name": "Storytelling with Data (Book)", "url": "https://www.storytellingwithdata.com/", "skill": "Data Visualization", "type": "Book"},

    # ── Docker / Kubernetes ───────────────────────────────────────────────────
    {"name": "Docker Official Getting Started", "url": "https://docs.docker.com/get-started/", "skill": "Docker", "type": "Course"},
    {"name": "Kubernetes Official Tutorial", "url": "https://kubernetes.io/docs/tutorials/", "skill": "Kubernetes", "type": "Course"},

    # ── dbt ───────────────────────────────────────────────────────────────────
    {"name": "dbt Documentation", "url": "https://docs.getdbt.com/", "skill": "dbt", "type": "Article"},
    {"name": "dbt Learn (Free Course)", "url": "https://courses.getdbt.com/", "skill": "dbt", "type": "Course"},

    # ── Excel ─────────────────────────────────────────────────────────────────
    {"name": "ExcelJet Formulas Guide", "url": "https://exceljet.net/formulas", "skill": "Excel", "type": "Article"},

    # ── General Interview Prep ────────────────────────────────────────────────
    {"name": "Ace the Data Science Interview (Book)", "url": "https://www.acethedatascienceinterview.com/", "skill": "Data Science", "type": "Book"},
    {"name": "InterviewQuery Practice", "url": "https://www.interviewquery.com/", "skill": "Data Science", "type": "Tool"},
]
