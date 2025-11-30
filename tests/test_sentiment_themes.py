import pytest
import pandas as pd
from Scripts.sentiment_themes import SentimentThemesAnalyzer
from Scripts.config import DATA_PATHS
from unittest.mock import patch

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'review_id': ['1', '2'],
        'review_text': ['Great app, fast transfers!', 'Slow login, crashes often.'],
        'rating': [5, 1],
        'bank_name': ['CBE', 'BOA'],
        'review_date': ['2025-01-01', '2025-01-02']
    })

def test_compute_sentiment(sample_df):
    analyzer = SentimentThemesAnalyzer(use_distilbert=False)
    analyzer.df = sample_df
    analyzer.stats = {'original_count': len(sample_df)}

    with patch.object(analyzer.vader_analyzer, 'polarity_scores',
                      side_effect=[{'compound': 0.6}, {'compound': -0.7}]):
        analyzer.compute_sentiment()

    assert analyzer.df['sentiment_label'].iloc[0] == 'positive'
    assert analyzer.df['sentiment_score'].iloc[1] < 0
    assert analyzer.stats['sentiment_coverage'] == 100.0

def test_cluster_themes(sample_df):
    analyzer = SentimentThemesAnalyzer()
    analyzer.df = sample_df
    analyzer.cluster_themes()
    assert 'Transaction Speed; UI/UX' in analyzer.df['identified_themes'].values  # From 'transfers'
    assert len(analyzer.theme_examples) > 0