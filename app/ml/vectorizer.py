import math
import re
from collections import Counter
from typing import List, Dict, Tuple
import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer as SklearnTfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

class FallbackTfidfVectorizer:
    """
    Pure Python / NumPy TF-IDF Vectorizer that strictly adheres to
    scikit-learn's standard TF-IDF and Cosine Similarity formula:
    IDF(t) = ln((1 + N) / (1 + df(t))) + 1
    with L2 vector normalization.
    Ensures zero downtime on systems where native C-extension DLLs are policy restricted.
    """
    def __init__(self, max_features: int = 5000, stop_words: str = "english", ngram_range: Tuple[int, int] = (1, 2), sublinear_tf: bool = False):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.vocabulary_: Dict[str, int] = {}
        self.idf_diag_: np.ndarray = np.array([])
        self.num_docs_ = 0

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9+#./-]{2,}\b", text.lower())
        tokens = list(words)
        if self.ngram_range[1] >= 2 and len(words) >= 2:
            for i in range(len(words) - 1):
                tokens.append(f"{words[i]} {words[i+1]}")
        return tokens

    def fit(self, raw_documents: List[str]):
        doc_counters = [Counter(self._tokenize(doc)) for doc in raw_documents]
        self.num_docs_ = len(doc_counters)

        df: Counter = Counter()
        for c in doc_counters:
            for term in set(c.keys()):
                df[term] += 1

        # Select top max_features
        most_common = df.most_common(self.max_features)
        self.vocabulary_ = {term: idx for idx, (term, _) in enumerate(most_common)}

        # Compute smooth IDF: ln((1 + N) / (1 + df)) + 1
        idfs = []
        for term, idx in sorted(self.vocabulary_.items(), key=lambda x: x[1]):
            term_df = df[term]
            idf = math.log((1 + self.num_docs_) / (1 + term_df)) + 1.0
            idfs.append(idf)
        self.idf_diag_ = np.array(idfs)
        return self

    def transform(self, raw_documents: List[str]) -> np.ndarray:
        vocab_size = len(self.vocabulary_)
        if vocab_size == 0:
            return np.zeros((len(raw_documents), 1))

        matrix = np.zeros((len(raw_documents), vocab_size), dtype=np.float64)
        for doc_idx, doc in enumerate(raw_documents):
            counts = Counter(self._tokenize(doc))
            for term, count in counts.items():
                if term in self.vocabulary_:
                    t_idx = self.vocabulary_[term]
                    matrix[doc_idx, t_idx] = count

        # Multiply by IDF
        matrix = matrix * self.idf_diag_

        # L2 normalize rows
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def fit_transform(self, raw_documents: List[str]) -> np.ndarray:
        return self.fit(raw_documents).transform(raw_documents)


def compute_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between two feature matrices."""
    if SKLEARN_AVAILABLE:
        try:
            return sklearn_cosine_similarity(vec_a, vec_b)
        except Exception:
            pass
    # Pure numpy cosine similarity
    dot = np.dot(vec_a, vec_b.T)
    norm_a = np.linalg.norm(vec_a, axis=1, keepdims=True)
    norm_b = np.linalg.norm(vec_b, axis=1, keepdims=True)
    norm_a[norm_a == 0] = 1.0
    norm_b[norm_b == 0] = 1.0
    return dot / (norm_a * norm_b.T)

def get_tfidf_vectorizer(max_features: int = 5000):
    if SKLEARN_AVAILABLE:
        try:
            return SklearnTfidfVectorizer(max_features=max_features, stop_words="english", ngram_range=(1, 2))
        except Exception:
            pass
    return FallbackTfidfVectorizer(max_features=max_features, ngram_range=(1, 2))
