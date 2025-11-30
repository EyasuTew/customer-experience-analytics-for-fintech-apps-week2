"""
Sentiment and Thematic Analysis Script
Task 2: Quantify sentiment and identify themes

- Sentiment: DistilBERT (or VADER fallback)
- Themes: TF-IDF keywords + rule-based clustering into 4-5 categories per bank
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
import spacy  # For preprocessing
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # Fallback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .config import DATA_PATHS

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load spaCy model (run 'python -m spacy download en_core_web_sm' once)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.error("Run: python -m spacy download en_core_web_sm")
    sys.exit(1)

class SentimentThemesAnalyzer:
    """Analyzer for sentiment and themes"""

    def __init__(self, input_path=None, output_path=None, use_distilbert=True):
        self.input_path = input_path or DATA_PATHS['processed_reviews']
        self.output_path = output_path or DATA_PATHS['sentiment_results']
        self.df = None
        self.stats = {}
        self.use_distilbert = use_distilbert  # Flag for DistilBERT vs. VADER
        self.sentiment_pipeline = None
        self.vader_analyzer = None
        self._init_models()

    def _init_models(self):
        """Initialize sentiment models"""
        if self.use_distilbert:
            try:
                tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
                model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
                self.sentiment_pipeline = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
                logger.info("DistilBERT model loaded")
            except Exception as e:
                logger.warning(f"DistilBERT failed: {e}. Falling back to VADER.")
                self.use_distilbert = False
        if not self.use_distilbert:
            self.vader_analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER analyzer loaded")

    def load_data(self):
        """Load processed reviews"""
        logger.info("Loading processed data...")
        try:
            self.df = pd.read_csv(self.input_path)
            logger.info(f"Loaded {len(self.df)} reviews")
            self.stats['original_count'] = len(self.df)
            return True
        except Exception as e:
            logger.error(f"Failed to load: {e}")
            return False

    def preprocess_text_for_nlp(self, text):
        """Tokenize, remove stopwords, lemmatize"""
        if pd.isna(text) or text == '':
            return ''
        doc = nlp(text.lower())
        tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
        return ' '.join(tokens)

    def compute_sentiment(self):
        """Compute sentiment scores"""
        logger.info("Computing sentiment...")
        sentiments = []

        def get_distilbert_score(text):
            if len(text) > 512:  # Truncate for model
                text = text[:512]
            result = self.sentiment_pipeline(text)[0]
            score = result['score'] if result['label'] == 'POSITIVE' else -result['score']
            label = 'positive' if score > 0 else 'negative' if score < 0 else 'neutral'
            return label, score

        def get_vader_score(text):
            vs = self.vader_analyzer.polarity_scores(text)
            compound = vs['compound']
            label = 'positive' if compound >= 0.05 else 'negative' if compound <= -0.05 else 'neutral'
            return label, compound

        for idx, row in self.df.iterrows():
            text = row['review_text']
            if self.use_distilbert:
                label, score = get_distilbert_score(text)
            else:
                label, score = get_vader_score(text)
            sentiments.append({'sentiment_label': label, 'sentiment_score': score})

        sentiment_df = pd.DataFrame(sentiments)
        self.df = pd.concat([self.df.reset_index(drop=True), sentiment_df], axis=1)
        self.stats['sentiment_coverage'] = len(self.df) / self.stats['original_count'] * 100

        # Aggregate by bank and rating
        agg = self.df.groupby(['bank_name', 'rating'])['sentiment_score'].agg(['mean', 'count']).reset_index()
        logger.info("Sentiment Aggregates:\n" + agg.to_string())
        self.stats['aggregates'] = agg.to_dict('records')

    def extract_keywords(self, ngrams=(1, 2), top_k=20):
        """TF-IDF for keywords/ngrams per bank"""
        logger.info("Extracting keywords...")
        keywords_by_bank = {}

        def get_ngrams(text, n):
            doc = nlp(self.preprocess_text_for_nlp(text))
            return [' '.join([t.lemma_ for t in sent]) for sent in doc.sents for t in [tuple(ngram) for ngram in zip(*[iter([token.lemma_ for token in sent if token.is_alpha and not token.is_stop])] * n)] if len(ngram) == n]

        for bank in self.df['bank_name'].unique():
            bank_df = self.df[self.df['bank_name'] == bank]
            texts = bank_df['review_text'].apply(self.preprocess_text_for_nlp)

            vectorizer = TfidfVectorizer(max_features=1000, ngram_range=ngrams, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()

            # Top keywords
            top_indices = tfidf_matrix.sum(axis=0).argsort()[0, -top_k:][::-1]
            # keywords_by_bank[bank] = [
            #     (feature_names[i], tfidf_matrix[:, i].toarray().ravel().mean())
            #     for i in top_indices
            # ]

            col_means = np.array(tfidf_matrix.mean(axis=0)).ravel()

            keywords_by_bank[bank] = [
                (feature_names[i], col_means[i])
                for i in top_indices
            ]


            # keywords_by_bank[bank] = [(feature_names[i], tfidf_matrix[:, i].mean()) for i in top_indices]

        self.keywords_by_bank = keywords_by_bank
        logger.info("Top Keywords per Bank: " + str({k: [w[0] for w in v[:5]] for k, v in keywords_by_bank.items()}))

    def cluster_themes(self, num_themes=5):
        """Rule-based clustering of keywords into themes per bank"""
        logger.info("Clustering into themes...")
        # Documented grouping logic: Map keywords to themes based on domain knowledge (fintech pain points)
        # Themes: 1. Login/Access Issues (login, password, auth), 2. Transaction Speed (transfer, slow, load), 
        # 3. UI/UX (interface, easy, design), 4. Support (help, contact, response), 5. Features (new, add, update)
        theme_mapping = {
            'Login/Access Issues': ['login', 'password', 'auth', 'error', 'crash', 'freeze'],
            'Transaction Speed': ['transfer', 'slow', 'load', 'delay', 'transaction', 'payment'],
            'UI/UX': ['interface', 'easy', 'design', 'user', 'navigation', 'app'],
            'Customer Support': ['help', 'contact', 'support', 'response', 'chat'],
            'Feature Requests': ['new', 'add', 'update', 'feature', 'missing']
        }

        themes_by_review = []
        for idx, row in self.df.iterrows():
            text = self.preprocess_text_for_nlp(row['review_text']).lower()
            themes = []
            for theme, keywords in theme_mapping.items():
                if any(kw in text for kw in keywords):
                    themes.append(theme)
            themes_by_review.append('; '.join(themes) if themes else 'Other')

        self.df['identified_themes'] = themes_by_review

        # Per-bank theme counts (for 3+ themes KPI)
        theme_counts = self.df.groupby(['bank_name', 'identified_themes']).size().unstack(fill_value=0)
        logger.info("Theme Counts per Bank:\n" + theme_counts.to_string())
        self.stats['themes'] = theme_counts.to_dict()

        # Examples: Top 3 examples per theme/bank
        examples = {}
        for bank in self.df['bank_name'].unique():
            bank_df = self.df[self.df['bank_name'] == bank]
            for theme in theme_mapping.keys():
                theme_df = bank_df[bank_df['identified_themes'].str.contains(theme, na=False)]
                if len(theme_df) > 0:
                    ex = theme_df['review_text'].iloc[0][:100] + '...'
                    examples.setdefault(bank, {})[theme] = ex
        self.theme_examples = examples
        logger.info("Theme Examples: " + str(examples))

    def save_results(self):
        """Save enhanced CSV"""
        logger.info("Saving results...")
        try:
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            output_cols = ['review_id', 'review_text', 'sentiment_label', 'sentiment_score', 'identified_themes', 'rating', 'bank_name', 'review_date']
            self.df[output_cols].to_csv(self.output_path, index=False)
            logger.info(f"Saved to: {self.output_path}")
            self.stats['final_count'] = len(self.df)
            return True
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return False

    def generate_report(self):
        """Generate analysis report"""
        logger.info("=" * 60)
        logger.info("SENTIMENT & THEMES REPORT")
        logger.info("=" * 60)
        logger.info(f"Coverage: {self.stats['sentiment_coverage']:.1f}%")
        logger.info(f"Aggregates: {self.stats['aggregates']}")
        logger.info(f"Themes: {self.stats['themes']}")
        logger.info(f"Examples: {self.theme_examples}")

    def analyze(self):
        """Run full pipeline"""
        if not self.load_data():
            return False
        self.compute_sentiment()
        self.extract_keywords()
        self.cluster_themes()
        if self.save_results():
            self.generate_report()
            return True
        return False


def main():
    analyzer = SentimentThemesAnalyzer(use_distilbert=True)  # Set False for VADER
    success = analyzer.analyze()
    if success:
        logger.info("✓ Task 2 completed!")
        return analyzer.df
    return None


if __name__ == "__main__":
    df = main()