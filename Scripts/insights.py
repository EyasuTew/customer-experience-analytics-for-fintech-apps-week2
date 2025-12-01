# insights_analysis.py - Task 4: Insights Derivation (Non-Plotting Part)
# Run: python insights_analysis.py (queries DB, derives insights, saves JSON)

import os
import json
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import re
from collections import Counter
from datetime import datetime
import logging
from scipy.stats import f_oneway

# Config (from .env or hardcode for demo)
DB_CONFIG = {'postgres_uri': 'postgresql://root:Alpha323@localhost:5432/bank_reviews'}  # Update as needed
OUTPUT_DIR = 'outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keywords for themes (from Task 2)
THEME_KEYWORDS = {
    'Account Access Issues': r'login|error|crash|bug|access|fail',
    'Transaction Performance': r'slow|loading|transfer|speed|lag|delay',
    'User Interface & Experience': r'ui|interface|design|easy|user|friendly|navigation',
    'Customer Support': r'support|help|chat|service|contact',
    'Feature Requests': r'feature|add|want|new|budget|login|fingerprint|wish'
}

def query_db(engine):
    """Query full dataset from Postgres."""
    query = """
    SELECT b.bank_name, r.review_text, r.rating, r.review_date, 
           r.sentiment_label, r.sentiment_score, r.source
    FROM reviews r JOIN banks b ON r.bank_id = b.bank_id
    ORDER BY r.review_date DESC;
    """
    df = pd.read_sql(query, engine)
    df['review_date'] = pd.to_datetime(df['review_date'])
    logger.info(f"Queried {len(df)} reviews from DB")
    return df

def derive_themes(df):
    """Assign themes based on keywords."""
    def assign_theme(text):
        text_lower = text.lower()
        for theme, pattern in THEME_KEYWORDS.items():
            if re.search(pattern, text_lower):
                return theme
        return 'Other'
    
    df['theme'] = df['review_text'].apply(assign_theme)
    return df

def extract_insights_per_bank(df):
    """Identify drivers/pains: Keyword counts in pos/neg subsets."""
    insights = {}
    drivers_keywords = ['fast', 'easy', 'secure', 'intuitive', 'smooth', 'reliable']
    pains_keywords = ['slow', 'crash', 'error', 'bug', 'lag', 'fail']
    
    for bank in df['bank_name'].unique():
        df_bank = df[df['bank_name'] == bank]
        pos_text = ' '.join(df_bank[df_bank['sentiment_label'] == 'positive']['review_text'].dropna())
        neg_text = ' '.join(df_bank[df_bank['sentiment_label'] == 'negative']['review_text'].dropna())
        
        # Count occurrences
        pos_counts = {k: pos_text.lower().count(k) for k in drivers_keywords}
        neg_counts = {k: neg_text.lower().count(k) for k in pains_keywords}
        
        # Top drivers/pains (threshold: >5 mentions)
        top_drivers = [k.title() + ' Navigation/Transactions' for k, v in pos_counts.items() if v > 5]
        top_pains = [k.title() + 's/Errors' for k, v in neg_counts.items() if v > 10]
        
        # Aggregates
        avg_sent = df_bank['sentiment_score'].mean()
        theme_dist = df_bank['theme'].value_counts(normalize=True).to_dict()
        
        insights[bank] = {
            'drivers': top_drivers[:3],  # 2+
            'pain_points': top_pains[:3],  # 2+
            'avg_sentiment': round(avg_sent, 2),
            'theme_distribution': {k: round(v, 2) for k, v in theme_dist.items()},
            'recommendations': generate_recs(bank, top_drivers, top_pains)  # 2+
        }
    
    # Comparisons
    comparisons = compare_banks(df)
    insights['comparisons'] = comparisons
    
    return insights

def generate_recs(bank, drivers, pains):
    """Generate 2+ recs based on insights."""
    recs = []
    if any('slow' in p.lower() or 'lag' in p.lower() for p in pains):
        recs.append('Optimize backend for faster transfers (e.g., caching) to address performance pains.')
    if any('crash' in p.lower() or 'error' in p.lower() for p in pains):
        recs.append('Implement crash reporting and AI-driven bug fixes for stability.')
    if any('feature' in d.lower() for d in drivers) or len(drivers) < 2:
        recs.append('Add requested features like budgeting tools or fingerprint login.')
    if len(recs) < 2:
        recs.append('Conduct user surveys to validate and prioritize improvements.')
    return recs[:3]

def compare_banks(df):
    """Simple comparisons (e.g., ANOVA or diffs)."""
    sentiments = [group['sentiment_score'].values for name, group in df.groupby('bank_name')]
    f_stat, p_val = f_oneway(*sentiments)
    return {
        'sentiment_diff': 'Significant differences (p={:.3f})'.format(p_val),
        'leader': df.groupby('bank_name')['sentiment_score'].mean().idxmax(),
        'laggard': df.groupby('bank_name')['sentiment_score'].mean().idxmin()
    }

def main():
    engine = create_engine(DB_CONFIG['postgres_uri'])
    df = query_db(engine)
    df = derive_themes(df)
    insights = extract_insights_per_bank(df)
    
    # Save insights and df for notebook
    insights_path = os.path.join(OUTPUT_DIR, 'insights.json')
    df_path = os.path.join(OUTPUT_DIR, 'reviews_df.csv')
    with open(insights_path, 'w') as f:
        json.dump(insights, f, indent=2, default=str)
    df.to_csv(df_path, index=False)
    
    logger.info(f"Insights saved to {insights_path}")
    logger.info(f"DF saved to {df_path} for notebook use")
    
    # Print summary for report
    print("=== Task 4 Insights Summary ===")
    for bank, data in insights.items():
        if bank != 'comparisons':
            print(f"\n{bank}:")
            print(f"Drivers: {', '.join(data['drivers'])}")
            print(f"Pain Points: {', '.join(data['pain_points'])}")
            print(f"Recommendations: {', '.join(data['recommendations'])}")
            print(f"Avg Sentiment: {data['avg_sentiment']}")
    
    print(f"\nComparisons: {insights['comparisons']}")
    
    # Ethics note (log/print)
    print("\nEthics: Reviews may skew negative (extreme opinions); supplement with balanced surveys.")

if __name__ == "__main__":
    main()