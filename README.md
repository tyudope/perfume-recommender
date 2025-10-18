# 🌸 Perfume Recommender — AI/ML Project 

Find your next signature scent by describing what you like (e.g., *“Dior Sauvage, citrus, summer, office”*), and get smart recommendations with clear explanations.

**Live demo:** https://perfume-recommender-vj81.onrender.com

> Built for speed and clarity: FastAPI backend, semantic similarity + rule filters, optional LLM “why” reasoning, clean beige UI.
> A hybrid recommendation system that blends **semantic retrieval**, **heuristic ranking**, and **GenAI explanations** to suggest fragrances based on user taste, use-cases, and constraints. Built with **FastAPI + Pandas + Vanilla JS**.

---
---

## Table of Contents

1. [Project Goals](#project-goals)  
2. [High-Level Architecture](#high-level-architecture)  
3. [Data: Collection → Cleaning → Final Schema](#data-collection--cleaning--final-schema)  
4. [Algorithms: Retrieval, Scoring, Explainability](#algorithms-retrieval-scoring-explainability)  
5. [Backend API](#backend-api)  
6. [Frontend UX & Accessibility](#frontend-ux--accessibility)  
7. [Configuration & Environment](#configuration--environment)  
8. [Security, Secrets & Cost Controls](#security-secrets--cost-controls)  
9. [Local Development & Running](#local-development--running)  
10. [Testing & Quality](#testing--quality)  
11. [Performance Notes](#performance-notes)  
12. [Troubleshooting](#troubleshooting)  
13. [Roadmap / Future Work](#roadmap--future-work)  
14. [Author](#author)  
15. [License](#license)

---

## Project Goals

- Build an **explainable perfume recommender** that feels natural for users who think in notes, vibes, and occasions (e.g., *“fresh office summer”*).  
- Keep stack **simple and transparent** so recruiters can quickly see the ML/IR decisions.  
- Provide **clear separation** of concerns: retrieval (semantic similarity), ranking (signals), and explainability (LLM).  
- Make it **safe to demo locally** without racking up unexpected LLM costs.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                            Frontend (Jinja2 + Vanilla JS)        │
│  index.html  style.css  app.js                                    │
│  - Inputs: liked perfumes, notes, filters, use-case chips         │
│  - Renders cards, stars, AI reasoning (“AI says”)                 │
└──────────────┬────────────────────────────────────────────────────┘
               │  POST /api/recommend (JSON)
┌──────────────▼────────────────────────────────────────────────────┐
│                          FastAPI Backend                          │
│  main.py                                                          │
│  - Loads perfumes.csv                                             │
│  - Vector store query (content similarity)                        │
│  - Filter + composite scoring                                     │
│  - Optional LLM explanation (providers.py)                        │
└──────────────┬────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────┐    ┌───────────────────────────────────┐
│  vectorstore.py          │    │ providers.py (OpenAI)             │
│  - Build text corpus     │    │ - Reads OPENAI_API_KEY            │
│  - Fit TF‑IDF encoder    │    │ - Chat completions for reasoning  │
│  - Cosine similarity     │    └───────────────────────────────────┘
└──────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│                              data/perfumes.csv                    │
│  brand,name,gender,price_min,price_max,main_accords,              │
│  longevity,sillage,rating_value,rating_count,description,url      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data: Collection → Cleaning → Final Schema

### 1) Collection
- Source: **Fragrantica** dataset (public datasets and community exports).  
- Strategy: prefer datasets that include **brand, name, accords, description, rating, longevity, sillage**.  
- Downloaded raw CSV/JSON and placed an intermediate file in `data/` (not committed if license-sensitive).

### 2) Cleaning
Implement a small cleaning script (example `scripts/clean_fragrantica.py` or integrated in your pipeline):

- **Normalize column names** → lowercase + underscores (e.g., `Rating Value → rating_value`).  
- **Select columns** → keep only fields the recommender uses.  
- **Price** → convert to PLN where possible or set approximate ranges (optional).  
- **Text normalization** → strip whitespace, fill empties with `""`.  
- **Numeric coercion** → `pd.to_numeric(..., errors="coerce")` then fill NaNs with defaults.  
- **Accords** → ensure `main_accords` is a single `|`-separated string (e.g., `"citrus|woody|aromatic"`).  
- **Gender** → standardize to `Male`, `Female`, `Unisex`; infer from description if missing (regex).  
- **URL** → keep a `url` column for users to click through to Fragrantica.

> See `main.py::load_df()` for robust loading and type coercion.

### 3) Final Schema (perfumes.csv)
Minimal columns used by the system:

| Column          | Type     | Example                                 |
|-----------------|----------|-----------------------------------------|
| brand           | str      | `Dior`                                  |
| name            | str      | `Sauvage`                               |
| gender          | str      | `Male` / `Female` / `Unisex`            |
| price_min       | float    | `280`                                   |
| price_max       | float    | `500`                                   |
| main_accords    | str      | `citrus|woody|aromatic`                 |
| longevity       | float    | `4.0`                                   |
| sillage         | float    | `3.5`                                   |
| rating_value    | float    | `4.3`                                   |
| rating_count    | int      | `1200`                                  |
| description     | str      | short textual description               |
| url             | str      | `https://www.fragrantica.com/...`       |

---

## Algorithms: Retrieval, Scoring, Explainability

### 1) Retrieval (Content-Based Similarity)
- Build a text corpus per perfume:
  ```
  text = f"{brand} {name}. accords: {main_accords}. {description}"
  ```
- Fit **TF‑IDF** vectorizer (or embeddings if configured) → `vectorstore.py`.
- Convert user query to text:
  ```
  query_text = " ".join(liked + preferred_notes) or "fresh versatile office citrus"
  ```
- Compute **cosine similarity** between query vector and item vectors.
- Keep similarity scores as `content_sim` and pass to the ranker.

### 2) Heuristic Filters
Apply hard filters to prune the search space:
```
price_min/max, rating_min, rating_count_min, longevity_min, sillage_min, gender
```

### 3) Use‑Case Fit
Map use-cases (chips: `office`, `date`, `summer`, `winter`) to accords or tags and compute a **set-overlap score** in `recommender.py`:
```
usecase_score = |intersection| / |union|  in [0, 1]
```

### 4) Composite Scoring
Weighted linear combination (tuned for intuitive results):
```
score = 0.40 * content_sim
      + 0.15 * usecase
      + 0.15 * longevity_norm     (longevity / 5)
      + 0.20 * rating_norm        (rating_value / 5)
      + 0.10 * rating_count_norm  (min(rating_count/2000, 1))
```

### 5) Explainability (Optional GenAI Layer)
For the top `N` items (capped), call the LLM with **only** the data we show to users and ask for **two concise bullets** explaining the match.  
- Model: `gpt-4o-mini` (configurable).  
- Provider code: `providers.py` (reads key from `.env`, uses `/chat/completions` with `response_format=json_object`).  
- Output attached as `ai_why` per item and rendered on the card.

---

## Backend API

### Endpoints
- `GET /` → main UI (Jinja template)  
- `GET /intro` → how-to guide  
- `GET /about` → algorithm page  
- `GET /api/health` → `{ ok: true, catalog_size: <int> }`  
- `POST /api/recommend` → returns recommendations

### Request (JSON)
```json
{
  "liked": ["Dior Sauvage", "Bleu de Chanel"],
  "preferred_notes": ["citrus", "woody"],
  "use_cases": ["office", "summer"],
  "price_min": 200,
  "price_max": 900,
  "rating_min": 0,
  "rating_count_min": 0,
  "longevity_min": 0,
  "sillage_min": 0,
  "gender": "Male",
  "k": 8,
  "explain": true
}
```

### Response (JSON)
```json
{
  "llm_used": true,
  "results": [
    {
      "brand": "Chanel",
      "name": "Bleu de Chanel",
      "gender": "Male",
      "price_range": [350, 600],
      "accords": ["citrus", "woody", "aromatic"],
      "longevity": 4.2,
      "sillage": 3.8,
      "rating_value": 4.5,
      "rating_count": 15400,
      "url": "https://...",
      "description": "Fresh woody aromatic...",
      "score": 0.547,
      "why": "matches your scent profile; fits your use-cases; long-lasting performance",
      "ai_why": "• Shares citrus–woody DNA you enjoy\n• Versatile for office and warm weather"
    }
  ]
}
```

---

## Frontend UX & Accessibility

- **Chips** (office/date/summer/winter) act as toggles — hover/active effects and keyboard focus possible.  
- **Star UI** shows **rating, longevity, sillage** (1–5).  
- **AI box** (“💡 AI says”) appears only if explanations are enabled and returned.  
- **Fragrantica link** on each card (`url`) for deeper exploration.  
- **ARIA**: results container has `aria-live="polite"` to announce updates.

---

## Configuration & Environment

Create `backend/.env` (not committed):
```
# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

# Safety caps
MAX_K=10
MAX_LLM_EXPLAINS=5
```

- The provider accepts **either** `OPENAI_API_KEY` or `LLM_API_KEY`, and **either** `OPENAI_MODEL` or `LLM_MODEL`.  
- `MAX_LLM_EXPLAINS` caps how many top results get AI bullets per request.

---

## 🛡️ Security, Secrets & Cost Controls

- **No API keys in Git**  
  `.env` is ignored via `.gitignore`. Only `.env.example` (without real secrets) is versioned for reference.  

- **Server-side key protection**  
  The OpenAI API key is **only used inside [`providers.py`](backend/app/providers.py)** — it is never exposed to the frontend or browser requests. All LLM calls happen securely on the backend.  

- **Input validation**  
  The [`RecommendRequest`](backend/app/main.py) Pydantic model enforces strict type checking and reasonable bounds (e.g., `k ≤ MAX_K`, price filters ≥ 0).  

- **Daily IP-based quota**  
  Each client IP is limited to a configurable number of AI reasoning requests per day (`LLM_DAILY_LIMIT`), with an automatic 24-hour reset. This prevents abuse and controls API costs.  

- **Explain cap per request**  
  `MAX_LLM_EXPLAINS` ensures each AI reasoning call only explains a limited number of perfumes, protecting per-request costs and response time.  

- **Frontend safeguards**  
  The UI prevents excessive LLM usage and **visually indicates** when the AI reasoning is capped or near limit (red badges + smooth fade-in warning banner).  

- **Abuse protection (optional)**  
  Additional middleware such as `slowapi` or Redis-backed rate limiting can be added if deploying publicly or at scale.  

- **Safe logging**  
  Logs capture only high-level actions and errors — never personal data, API keys, or full request bodies.

---

## Local Development & Running

```bash
## 🚀 Quickstart (Local)
Requirements: Python 3.9+


git clone https://github.com/tyudope/perfume-recommender.git
cd perfume-recommender

# create & activate venv (optional)
python3 -m venv .venv && source .venv/bin/activate

# install backend deps
pip install -r backend/requirements.txt

# set environment
cp backend/.env.example backend/.env
# edit backend/.env and fill LLM_API_KEY, adjust limits if you want

# run
uvicorn --app-dir backend app.main:app --reload --host 0.0.0.0 --port 8000


Open http://localhost:8000
```

**Dev Tips**
- Use a branch (e.g., `git checkout -b ai-explanations`) for experiments.  
- Hard refresh the browser to bust static caching: `Cmd/Ctrl + Shift + R`.

---

## Testing & Quality


- **Smoke tests**:
  - `/api/health` returns `ok: true`
  - `/api/recommend` returns results for a simple payload
  - LLM disabled → app still works (no `ai_why` fields)
- **Data checks**:
  - Required columns exist in `perfumes.csv`
  - No critical columns all-null
  - Reasonable value ranges

---

## Performance Notes

- **Cold start**: TF‑IDF fit happens once at startup; keep `perfumes.csv` compact (tens of thousands of rows is fine).  
- **Runtime**: Query-time involves a single cosine similarity + Pandas filtering + ranking → typically low latency on laptop hardware.  
- **LLM**: Explanations add network latency; capped by `MAX_LLM_EXPLAINS` to keep UX snappy.

---

## Troubleshooting

- **Styles missing on /intro or /about** → ensure `<link rel="stylesheet" href="/static/style.css">` (absolute path) and `.container` wrapper.  
- **No AI box appears**:
  - Check that the UI sends `"explain": true`.
  - Verify `llm_available()` returns `True` (env key loaded).
  - Check console/logs for 401/429 from OpenAI.
- **CSV load error** → check delimiter (`,`), encoding (`utf-8`), and column names.  
- **CORS** → backend sets permissive CORS in dev; tighten for prod as needed.

---

## Roadmap / Future Work

- ✨ Switch from TF‑IDF to **OpenAI text embeddings** (`text-embedding-3-small`) + ANN index.  
- 👥 Add collaborative filtering (implicit feedback) for personalization.  
- 🌐 Multilingual support (Polish/Turkish/English).  
- 🧪 A/B testing of scoring weights, automated tuning.  
- 🔐 Auth + saved profiles; opt-in telemetry for offline evaluation.  
- 📊 Offline evaluation notebook against held-out “similar perfume” pairs.

---

## Author

**Selim Dalçiçek** — Polish-Japanese Academy of Information Technology (PJATK)  
Aspiring Machine Learning Engineer | Data Science Enthusiast · Warsaw, Poland

---

## License

This project is released under the **MIT License**. Feel free to use and adapt with attribution.
