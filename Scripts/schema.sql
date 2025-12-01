
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
);