
import pytest
import pandas as pd
from Scripts.preprocessing import ReviewPreprocessor
import os

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'review_id': ['1', '2', '1'],  # Duplicate
        'review_text': ['Good app', 'Bad UI', None],
        'rating': [5, 0, 3],  # Invalid rating
        'review_date': ['2023-01-01', '2023-01-02', 'invalid_date'],
        'bank_name': ['CBE', None, 'BOA'],
        'user_name': [None, 'User2', 'User3'],
        'thumbs_up': [10, None, 5],
        'reply_content': ['Reply1', None, None],
        'source': ['Google Play'] * 3
    })

def test_load_data(sample_df, tmp_path):
    # Test load/save with temp file
    input_path = tmp_path / 'raw.csv'
    sample_df.to_csv(input_path, index=False)
    preprocessor = ReviewPreprocessor(input_path=str(input_path))
    assert preprocessor.load_data()
    assert len(preprocessor.df) == 3

def test_remove_duplicates(sample_df):
    preprocessor = ReviewPreprocessor()
    preprocessor.df = sample_df
    preprocessor.remove_duplicates()
    assert len(preprocessor.df) == 2  # Removes 1 duplicate
    assert preprocessor.df['review_id'].nunique() == 2

def test_handle_missing_values(sample_df):
    preprocessor = ReviewPreprocessor()
    preprocessor.df = sample_df
    preprocessor.handle_missing_values()
    assert preprocessor.df['user_name'].isnull().sum() == 0
    assert len(preprocessor.df) == 1  # Drops 1 row with missing critical

def test_normalize_dates(sample_df):
    preprocessor = ReviewPreprocessor()
    preprocessor.df = sample_df.copy()  # Fix invalid date for test
    preprocessor.df['review_date'] = ['2023-01-01', '2023-01-02', '2023-01-03']
    preprocessor.normalize_dates()
    assert 'review_year' in preprocessor.df.columns
    assert preprocessor.df['review_year'].iloc[0] == 2023

def test_clean_text(sample_df):
    preprocessor = ReviewPreprocessor()
    preprocessor.df = sample_df
    preprocessor.clean_text()
    assert len(preprocessor.df) == 2  # Removes empty/None
    assert preprocessor.df['text_length'].iloc[0] > 0

def test_validate_ratings(sample_df):
    preprocessor = ReviewPreprocessor()
    preprocessor.df = sample_df
    preprocessor.validate_ratings()
    assert (preprocessor.df['rating'] >= 1).all() and (preprocessor.df['rating'] <= 5).all()