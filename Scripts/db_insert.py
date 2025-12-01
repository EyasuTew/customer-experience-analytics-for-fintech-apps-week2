"""
PostgreSQL Data Insertion Script
Task 3: Store cleaned data in relational DB

- Creates DB/tables if needed (with robust drops)
- Inserts from reviews_with_sentiment.csv
- Verifies with queries
"""

import os
import sys
import logging
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_PATHS, DB_CONFIG

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DBInserter:
    """Class for DB setup and insertion"""

    def __init__(self, db_uri=None, csv_path=None):
        self.db_uri = db_uri or DB_CONFIG['postgres_uri']
        self.csv_path = csv_path or DATA_PATHS['sentiment_results']  # From Task 2
        self.engine = create_engine(self.db_uri, echo=False)  # echo=True for debug
        self.stats = {}

    def create_database_and_tables(self):
        """Create DB and run schema with robust drops"""
        logger.info("Creating database and tables...")
        try:
            # Wrap in transaction for atomicity
            with self.engine.begin() as conn:  # Auto-commits on success, rolls back on error
                # Explicitly drop in order: dependent first
                conn.execute(text("DROP TABLE IF EXISTS reviews CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS banks CASCADE"))
                logger.info("Tables dropped successfully")

                # Create banks
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS banks (
                        bank_id SERIAL PRIMARY KEY,
                        bank_name VARCHAR(255) NOT NULL UNIQUE,
                        app_name VARCHAR(255) NOT NULL
                    )
                """))

                # Create reviews
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS reviews (
                        review_id VARCHAR(255) PRIMARY KEY,
                        bank_id INTEGER NOT NULL REFERENCES banks(bank_id) ON DELETE CASCADE,
                        review_text TEXT NOT NULL,
                        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                        review_date DATE NOT NULL,
                        sentiment_label VARCHAR(50),
                        sentiment_score DECIMAL(3,2),
                        source VARCHAR(50) DEFAULT 'Google Play',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # Indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reviews_bank_id ON reviews(bank_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment_score)"))

            logger.info("Tables created successfully")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Schema error: {e}")
            # Rollback is automatic in begin() block
            return False

    def insert_data(self):
        """Insert banks and reviews from CSV"""
        logger.info("Loading CSV...")
        try:
            df = pd.read_csv(self.csv_path)
            logger.info(f"Loaded {len(df)} records")
            self.stats['loaded'] = len(df)

            with self.engine.begin() as conn:  # Transaction for inserts
                # Insert unique banks (UPSERT)
                banks_data = []
                for _, row in df.iterrows():
                    if row['bank_name'] not in [b[0] for b in banks_data]:  # Dedupe
                        banks_data.append((row['bank_name'], 'Mobile Banking App'))  # Placeholder app_name

                for name, app in banks_data:
                    conn.execute(
                        text("INSERT INTO banks (bank_name, app_name) VALUES (:name, :app) "
                             "ON CONFLICT (bank_name) DO NOTHING"),
                        {'name': name, 'app': app}
                    )

                # Fetch bank_id map
                bank_map = {}
                result = conn.execute(text("SELECT bank_id, bank_name FROM banks"))
                for row in result:
                    bank_map[row[1]] = row[0]

                # Prepare and insert reviews as LIST OF DICTS (FIX: Matches param names)
                insert_data = []
                for _, row in df.iterrows():
                    if row['bank_name'] in bank_map:
                        insert_data.append({
                            'review_id': str(row['review_id']),  # Ensure string
                            'bank_id': bank_map[row['bank_name']],
                            'review_text': str(row['review_text']),
                            'rating': int(row['rating']) if pd.notna(row['rating']) else None,
                            'review_date': pd.to_datetime(row['review_date']).date() if pd.notna(row['review_date']) else None,
                            'sentiment_label': str(row['sentiment_label']) if pd.notna(row['sentiment_label']) else None,
                            'sentiment_score': float(row['sentiment_score']) if pd.notna(row['sentiment_score']) else None,
                            'source': str(row.get('source', 'Google Play'))
                        })

                if insert_data:
                    conn.execute(
                        text("INSERT INTO reviews (review_id, bank_id, review_text, rating, review_date, sentiment_label, sentiment_score, source) "
                             "VALUES (:review_id, :bank_id, :review_text, :rating, :review_date, :sentiment_label, :sentiment_score, :source) "
                             "ON CONFLICT (review_id) DO NOTHING"),
                        insert_data  # Now list of dicts
                    )

            self.stats['inserted_reviews'] = len(insert_data)
            logger.info(f"Inserted {len(insert_data)} reviews")
            return True
        except Exception as e:
            logger.error(f"Insertion error: {e}")
            return False

    def verify_data(self):
        """Run verification queries"""
        logger.info("Verifying data...")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT b.bank_name, COUNT(r.review_id) AS count, 
                           AVG(r.rating) AS avg_rating, AVG(r.sentiment_score) AS avg_sentiment
                    FROM banks b LEFT JOIN reviews r ON b.bank_id = r.bank_id
                    GROUP BY b.bank_id, b.bank_name ORDER BY count DESC
                """)).fetchall()
                logger.info("Reviews per Bank:")
                for row in result:
                    logger.info(f"  {row[0]}: {row[1]} reviews, Avg Rating: {row[2]:.2f}, Avg Sentiment: {row[3]:.2f}")

                total = conn.execute(text("SELECT COUNT(*) FROM reviews")).scalar()
                self.stats['total_reviews'] = total
                logger.info(f"Total reviews: {total}")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Verification error: {e}")
            return False

    def run(self):
        """Full pipeline"""
        if self.create_database_and_tables():
            if self.insert_data():
                if self.verify_data():
                    logger.info("✓ Task 3 complete!")
                    return self.stats
        return None


def main():
    inserter = DBInserter()
    stats = inserter.run()
    if stats:
        print(f"Success: {stats['total_reviews']} reviews inserted")
    else:
        print("Failed")


if __name__ == "__main__":
    main()