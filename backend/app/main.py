from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import pandas as pd

from .vectorstore import SimpleStore
from .recommender import accords_set, usecase_score, final_score

app = FastAPI(title="Perfume Recommender", version="0.2.0")
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "perfumes.csv"

# globals (built at startup)
DF: pd.DataFrame = pd.DataFrame()
STORE: SimpleStore = None  # type: ignore

def load_df():
    if DATA_PATH.exists():
        try:
            return pd.read_csv(DATA_PATH)
        except Exception as e:
            print("Failed to read perfumes.csv:", e)
    return pd.DataFrame()

class RecommendRequest(BaseModel):
    liked: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None         # e.g. ["office","summer"]
    preferred_notes: Optional[List[str]] = None   # e.g. ["citrus","woody"]
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    k: int = 8

@app.on_event("startup")
def _startup():
    global DF, STORE
    DF = load_df()
    STORE = SimpleStore(DF) if len(DF) else None
    print(f"Loaded catalog: {len(DF)} items")

@app.get("/api/health")
def health():
    return {"ok": True, "catalog_size": int(len(DF))}

@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    liked = req.liked or []
    use_cases = req.use_cases or []
    preferred_notes = req.preferred_notes or []

    if STORE is None or DF.empty:
        return {"results": [], "message": "Catalog is empty."}

    # Build a query from liked names + preferred notes
    liked_text = " ".join(liked)
    notes_text = " ".join(preferred_notes)
    query = (liked_text + " " + notes_text).strip() or "fresh versatile office citrus"

    # Base similarity
    sims = STORE.query_text(query)

    # Filter by price; exclude liked items
    candidates = DF.copy()
    if req.price_min is not None:
        candidates = candidates[candidates["price_min"] >= req.price_min]
    if req.price_max is not None:
        candidates = candidates[candidates["price_max"] <= req.price_max]
    if liked:
        candidates = candidates[~candidates["name"].isin(liked)]

    # Scores
    uc_scores = []
    lon_scores = []
    for _, row in candidates.iterrows():
        uc_scores.append(usecase_score(accords_set(row), use_cases))
        lon = (float(row.get("longevity", 3)) + float(row.get("sillage", 3))) / 10.0
        lon_scores.append(lon)

    candidates = candidates.assign(
        content_sim=sims[candidates.index],
        usecase=uc_scores,
        longevity=lon_scores
    )
    candidates["score"] = candidates.apply(
        lambda r: final_score(r["content_sim"], r["usecase"], r["longevity"]), axis=1
    )

    topk = candidates.sort_values("score", ascending=False).head(req.k)

    def why(row):
        bits = []
        if row["content_sim"] > 0.3: bits.append("similar scent profile to your picks")
        if row["usecase"] > 0.6: bits.append("fits your selected use-cases")
        if row["longevity"] > 0.6: bits.append("good longevity/sillage")
        return "; ".join(bits) or "balanced match"

    results = [{
        "brand": row["brand"],
        "name": row["name"],
        "score": round(float(row["score"]), 3),
        "price_range": [row.get("price_min"), row.get("price_max")],
        "accords": (row.get("main_accords") or "").split("|"),
        "why": why(row)
    } for _, row in topk.iterrows()]

    return {"results": results}