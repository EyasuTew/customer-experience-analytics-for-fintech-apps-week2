# Bank Reviews Analysis Project

## Overview
Analyzing customer satisfaction for Ethiopian mobile banking apps (CBE, BOA, Dashen Bank) via Google Play reviews. Focus: Scrape, preprocess, sentiment/themes, insights for retention/features/complaints.

## Methodology (Task 1)
- **Scraping**: `scraper.py` uses `google-play-scraper` (ref: https://github.com/anderskm/gplaycrawler) to fetch 400+ newest reviews/bank (1,200 total). Sorted by NEWEST, lang='en', country='et'.
- **Preprocessing**: `preprocessing.py` pipeline: Load → Check missing → Remove duplicates (by review_id) → Handle missing → Normalize dates (YYYY-MM-DD + year/month) → Clean text (dedupe whitespace, remove empty) → Validate ratings (1-5) → Sort (bank asc, date desc) → Save CSV.
- **Data Quality**: Targets <5% errors; logs retention rate.
- **EDA**: `preprocessing_EDA.ipynb` for ratings/date/length visuals.

## Setup
1. `pip install -r requirements.txt`
2. Set `.env` (APP_IDs optional; defaults in config.py).
3. Run notebook or `python scraper.py && python preprocessing.py`.

## Reports
See `Scripts/README.md` for stats.

## Branches
- `main`: Stable releases.
- `task-1`: Data collection/preprocessing.

## Test
- `pytest test\test_preprocessing.py -v`
- `pytest`




## Task 3: PostgreSQL Storage
- **Setup**: Install PostgreSQL (e.g., `brew install postgresql`; `createdb bank_reviews`). Run `psql -U postgres -d bank_reviews -f schema.sql`.
- **Insertion**: `python db_insert.py` (loads from Task 2 CSV; inserts 1,200+ rows).
- **Verification**: Queries in schema.sql; e.g., `SELECT COUNT(*) FROM reviews;` → 1,200.
- **Dump**: `pg_dump -U postgres bank_reviews > bank_reviews_dump.sql` (commit dump/schema).
- **Refs**: [SQLAlchemy Docs](https://docs.sqlalchemy.org/en/20/).

Run Instructions

1. Install Postgres: Windows: Download from postgresql.org. Mac: brew install postgresql && brew services start postgresql. 
2. Create user/DB: createuser -s postgres; createdb bank_reviews.
3. Env: Add to .env: DB_POSTGRES_URI=postgresql://postgres:yourpass@localhost:5432/bank_reviews.
4. git checkout -b task-3
5. pip install -r requirements.txt (includes psycopg2-binary).
6. Run schema: psql -U postgres -d bank_reviews -f schema.sql.
7. Ensure Task 2 CSV: Run notebook/script.
python db_insert.py (inserts >1,000; verifies).
Test Query: In psql: \i schema.sql (run verification at end).
Dump: pg_dump -U postgres -d bank_reviews > data/db_dump.sql (commit anonymized sample).

db schema

```
-- 1. Drop the child table first (the one with the foreign key)
DROP TABLE IF EXISTS reviews;

-- 2. Drop the parent table second
DROP TABLE IF EXISTS banks;

-- 3. Now recreate them
CREATE TABLE banks (
    bank_id SERIAL PRIMARY KEY,
    bank_name VARCHAR(255) NOT NULL UNIQUE,
    app_name VARCHAR(255) NOT NULL
);

CREATE TABLE reviews (
    review_id VARCHAR(255) PRIMARY KEY,
    bank_id INTEGER NOT NULL REFERENCES banks(bank_id) ON DELETE CASCADE,
    review_text TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    review_date DATE NOT NULL,
    sentiment_label VARCHAR(50),
    sentiment_score DECIMAL(3,2),
    source VARCHAR(50) DEFAULT 'Google Play',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);```