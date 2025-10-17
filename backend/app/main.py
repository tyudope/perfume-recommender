from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import pandas as pd
import os

# Local modules
from .vectorstore import SimpleStore
from .recommender import accords_set, usecase_score

# Optional: GenAI LLM explanations
try:
    from .providers import llm_available, llm_explain
except Exception:
    def llm_available() -> bool: return False
    def llm_explain(*args, **kwargs): return []

# --- Safety caps (prevent overuse) ---
MAX_K = int(os.getenv("MAX_K", "10"))
MAX_LLM_EXPLAINS = int(os.getenv("MAX_LLM_EXPLAINS", "5"))

# --- FastAPI setup ---
app = FastAPI(title="Perfume Recommender", version="0.5.1")

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = BASE_DIR / "data" / "perfumes.csv"

DF: pd.DataFrame = pd.DataFrame()
STORE: Optional[SimpleStore] = None


# === Load dataset ===
def load_df() -> pd.DataFrame:
    if DATA_PATH.exists():
        try:
            df = pd.read_csv(DATA_PATH)
            numeric_cols = [
                "price_min", "price_max",
                "longevity", "sillage",
                "rating_value", "rating_count"
            ]
            for c in numeric_cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            for c in ["brand", "name", "gender", "main_accords", "description", "url"]:
                if c in df.columns:
                    df[c] = df[c].fillna("")
            return df
        except Exception as e:
            print("⚠️ Failed to load perfumes.csv:", e)
    return pd.DataFrame()


# === Request schema ===
class RecommendRequest(BaseModel):
    liked: Optional[List[str]] = None
    preferred_notes: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    rating_min: Optional[float] = 0.0
    rating_count_min: Optional[int] = 0
    longevity_min: Optional[int] = 0
    sillage_min: Optional[int] = 0
    gender: Optional[str] = None
    k: int = Field(8, ge=1, le=10)   # <= 10
    explain: Optional[bool] = False


# === Startup event ===
@app.on_event("startup")
def _startup():
    global DF, STORE
    DF = load_df()
    STORE = SimpleStore(DF) if len(DF) else None
    print(f"✅ Loaded catalog: {len(DF)} perfumes")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/intro")
def intro(request: Request):
    return templates.TemplateResponse("intro.html", {"request": request})

@app.get("/about")
def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/api/health")
def health():
    return {"ok": True, "catalog_size": int(len(DF))}


# === Scoring helper ===
def _final_score(content_sim: float,
                 usecase: float,
                 longevity: float,
                 rating_value: float,
                 rating_count: float) -> float:
    """Composite weighted score."""
    rating_norm = max(min(rating_value / 5.0, 1.0), 0.0)
    count_norm = min(max(rating_count, 0.0) / 2000.0, 1.0)
    longevity_norm = max(min(longevity / 5.0, 1.0), 0.0)
    return (
        0.40 * float(content_sim)
        + 0.15 * float(usecase)
        + 0.15 * float(longevity_norm)
        + 0.20 * float(rating_norm)
        + 0.10 * float(count_norm)
    )


# === Main recommendation route ===
@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    if STORE is None or DF.empty:
        return {"results": [], "message": "Catalog is empty.", "llm_used": False}

    # --- Apply safety limits (do NOT disable explain; just cap how many we explain) ---
    k = min(int(req.k or 8), MAX_K)
    explain_n = min(MAX_LLM_EXPLAINS, k)

    liked = req.liked or []
    preferred_notes = req.preferred_notes or []
    use_cases = req.use_cases or []

    # --- Build semantic query ---
    query_text = " ".join(liked + preferred_notes).strip() or "fresh versatile office citrus"
    sims = STORE.query_text(query_text)

    candidates = DF.copy()

    # --- Apply filters ---
    if req.price_min is not None:
        candidates = candidates[candidates["price_min"] >= req.price_min]
    if req.price_max is not None:
        candidates = candidates[candidates["price_max"] <= req.price_max]
    if req.rating_min:
        candidates = candidates[candidates["rating_value"] >= req.rating_min]
    if req.rating_count_min:
        candidates = candidates[candidates["rating_count"] >= req.rating_count_min]
    if req.longevity_min:
        candidates = candidates[candidates["longevity"] >= req.longevity_min]
    if req.sillage_min:
        candidates = candidates[candidates["sillage"] >= req.sillage_min]
    if req.gender and req.gender.lower() not in ("any", "all", "none"):
        candidates = candidates[candidates["gender"].str.lower() == req.gender.lower()]
    if liked:
        candidates = candidates[~candidates["name"].str.lower().isin([s.lower() for s in liked])]

    if candidates.empty:
        return {"results": [], "message": "No matches after filters.", "llm_used": False}

    # --- Compute scores ---
    uc_scores = []
    for _, row in candidates.iterrows():
        uc_scores.append(usecase_score(accords_set(row), use_cases))
    content_sim = sims[candidates.index]

    scores = []
    for (idx, row), uc, cs in zip(candidates.iterrows(), uc_scores, content_sim):
        scores.append(_final_score(
            content_sim=cs,
            usecase=uc,
            longevity=float(row.get("longevity", 3) or 3),
            rating_value=float(row.get("rating_value", 0) or 0),
            rating_count=float(row.get("rating_count", 0) or 0),
        ))

    candidates = candidates.assign(
        content_sim=content_sim,
        usecase=uc_scores,
        score=scores
    )

    topk = candidates.sort_values("score", ascending=False).head(k)

    # --- Baseline reasoning ---
    def baseline_why(row) -> str:
        bits = []
        if row["content_sim"] > 0.3: bits.append("matches your scent profile")
        if row["usecase"] > 0.6: bits.append("fits your use-cases")
        try:
            if float(row.get("longevity", 0)) >= 4: bits.append("long-lasting performance")
        except Exception:
            pass
        try:
            if float(row.get("rating_value", 0)) >= 4.2 and float(row.get("rating_count", 0)) >= 200:
                bits.append("strong community ratings")
        except Exception:
            pass
        return "; ".join(bits) or "balanced match"

    results = []
    for _, row in topk.iterrows():
        results.append({
            "brand": row["brand"],
            "name": row["name"],
            "gender": row.get("gender", ""),
            "price_range": [int(row.get("price_min", 0) or 0), int(row.get("price_max", 0) or 0)],
            "accords": (row.get("main_accords") or "").split("|"),
            "longevity": float(row.get("longevity", 0) or 0),
            "sillage": float(row.get("sillage", 0) or 0),
            "rating_value": float(row.get("rating_value", 0) or 0),
            "rating_count": int(row.get("rating_count", 0) or 0),
            "url": row.get("url", ""),
            "description": row.get("description", ""),
            "score": round(float(row["score"]), 3),
            "why": baseline_why(row),
        })

    # --- LLM reasoning (explain up to explain_n results) ---
    llm_used = False
    if getattr(req, "explain", False) and llm_available() and results:
        explain_slice = results[:explain_n]
        context = {
            "liked": liked,
            "use_cases": use_cases,
            "preferred_notes": preferred_notes,
            "budget": f"{req.price_min}–{req.price_max} PLN"
                       if (req.price_min or req.price_max) else "unspecified",
        }
        ai_texts = llm_explain(context, explain_slice)
        if any(ai_texts):
            for i, txt in enumerate(ai_texts):
                if txt and i < len(results):
                    results[i]["ai_why"] = txt
            llm_used = True

    return {"results": results, "llm_used": llm_used}