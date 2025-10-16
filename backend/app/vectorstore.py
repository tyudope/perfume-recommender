import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SimpleStore:
    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)

        def norm(series: pd.Series) -> pd.Series:
            if series is None:
                return pd.Series([""] * len(self.df))
            return series.fillna("").astype(str).str.replace("|", " ").str.lower()

        corpus = (
            norm(self.df.get("description")) + " " +
            norm(self.df.get("main_accords")) + " " +
            norm(self.df.get("top_notes")) + " " +
            norm(self.df.get("middle_notes")) + " " +
            norm(self.df.get("base_notes"))
        )

        self.vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
        self.X = self.vec.fit_transform(corpus)

    def query_text(self, text: str):
        q = self.vec.transform([text.lower()])
        sims = cosine_similarity(q, self.X).ravel()
        return sims