import pandas as pd
import numpy as np
import re
from urllib.parse import urlparse, unquote
from pathlib import Path

RAW_PATH = Path("/Users/selimdalcicek/Desktop/Computer Science/perfume-recommender/backend/data/raw_fragrantica.csv")
OUT_PATH = Path("/Users/selimdalcicek/Desktop/Computer Science/perfume-recommender/backend/data/perfumes.csv")

# ---------- helpers ----------

import re

import re

FEMALE_PATTERNS = [
    r"\bfor women\b", r"\bfor woman\b", r"\bfor her\b",
    r"\bfemme\b", r"\bpour femme\b", r"\bwomen'?s\b", r"\bwomen\b", r"\bwoman\b",
    r"\bdonna\b", r"\bfemmes?\b"
]
MALE_PATTERNS = [
    r"\bfor men\b", r"\bfor man\b", r"\bfor him\b",
    r"\bhomme\b", r"\bpour homme\b", r"\bmen'?s\b", r"\bmen\b", r"\bman\b",
    r"\buomo\b", r"\bhommes?\b"
]
UNISEX_PATTERNS = [
    r"\bunisex\b", r"\bshared\b", r"\buniversal\b", r"\bfor (?:both|all)\b",
    r"\bfor women and men\b", r"\bfor men and women\b", r"\bfor (?:him|her)\b", r"\bfor her and him\b",
]

def _norm(s):
    if not isinstance(s, str):
        return ""
    return s.strip().lower()

def _any_match(patterns, text):
    return any(re.search(p, text) for p in patterns)

def infer_gender(raw_gender, name_hint="", desc_hint=""):
    """
    Priority:
      1) explicit dataset gender
      2) description hints
      3) name hints
      else Unisex
    """
    g = _norm(raw_gender)
    n = _norm(name_hint)
    d = _norm(desc_hint)

    # 1) dataset gender
    if _any_match(UNISEX_PATTERNS, g): return "Unisex"
    if _any_match(MALE_PATTERNS, g) or g in {"male", "m"}: return "Male"
    if _any_match(FEMALE_PATTERNS, g) or g in {"female", "f"}: return "Female"

    # 2) description hints
    if _any_match(UNISEX_PATTERNS, d): return "Unisex"
    if _any_match(MALE_PATTERNS, d): return "Male"
    if _any_match(FEMALE_PATTERNS, d): return "Female"

    # 3) name hints
    if _any_match(UNISEX_PATTERNS, n): return "Unisex"
    if _any_match(MALE_PATTERNS, n): return "Male"
    if _any_match(FEMALE_PATTERNS, n): return "Female"

    return "Unisex"



def one_liner(text: str) -> str:
    """Return a compact 1-line description (<= 240 chars)."""
    if not isinstance(text, str):
        return ""
    # take first sentence-ish, remove extra whitespace
    s = re.split(r"[.!?]\s", text.strip())[0]
    return re.sub(r"\s+", " ", s)[:240]

def parse_brand_name_from_url(u: str):
    """
    Expected Fragrantica URL:
      https://www.fragrantica.com/perfume/<Brand>/<Perfume>-<id>.html
    We extract <Brand> and <Perfume> safely.
    """
    try:
        path = unquote(urlparse(str(u)).path)  # /perfume/Dior/Sauvage-12345.html
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0].lower() == "perfume":
            brand = parts[1].replace("-", " ").strip()
            perfume_seg = parts[2].replace(".html", "")
            perfume = re.sub(r"-\d+$", "", perfume_seg)  # drop trailing -12345
            # Title case words (keep apostrophes and d’)
            brand = " ".join(w.capitalize() for w in brand.split())
            perfume = " ".join(w.capitalize() for w in perfume.replace("-", " ").split())
            return brand, perfume
    except Exception:
        pass
    return None, None

def fallback_brand_name(name: str):
    """
    Fallback: split the first token as brand, remainder as name.
    Not perfect, but better than Unknown.
    """
    if not isinstance(name, str) or not name.strip():
        return "Unknown", ""
    toks = name.strip().split()
    if len(toks) == 1:
        return toks[0], toks[0]
    return toks[0], " ".join(toks[1:])

def normalize_accords(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return (
        s.replace("/", "|")
         .replace(",", "|")
         .replace("  ", " ")
         .replace(" |", "|")
         .replace("| ", "|")
         .strip()
         .lower()
    )

# ---------- main ----------

def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw file not found: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)

    # Tolerant column-name handling
    cols = {c.lower(): c for c in df.columns}
    name_col = cols.get("name")
    gender_col = cols.get("gender")
    rating_val_col = cols.get("rating value") or cols.get("rating_value")
    rating_cnt_col = cols.get("rating count") or cols.get("rating_count")
    accords_col = cols.get("main accords") or cols.get("main_accords") or cols.get("accords")
    desc_col = cols.get("description")
    url_col = cols.get("url")

    # Minimal checks
    if not name_col or not gender_col or not accords_col:
        raise ValueError(
            "CSV must contain at least Name, Gender, Main Accords columns.\n"
            f"Found columns: {list(df.columns)}"
        )

    work = pd.DataFrame({
        "Name": df[name_col],
        "Gender": df[gender_col],
        "MainAccords": df[accords_col],
        "Description": df[desc_col] if desc_col else "",
        "URL": df[url_col] if url_col else "",
        "rating_value_raw": df[rating_val_col] if rating_val_col else 0,
        "rating_count_raw": df[rating_cnt_col] if rating_cnt_col else 0,
    })

    # Parse brand & name from URL (best), fallback to naive split on Name
    parsed = work["URL"].apply(parse_brand_name_from_url)
    work["brand"] = [p[0] if p and p[0] else None for p in parsed]
    work["name"] = [p[1] if p and p[1] else None for p in parsed]

    missing_mask = work["brand"].isna() | work["name"].isna()
    if missing_mask.any():
        fb = work.loc[missing_mask, "Name"].apply(fallback_brand_name)
        fb_brand = [x[0] for x in fb]
        fb_name = [x[1] for x in fb]
        work.loc[missing_mask, "brand"] = fb_brand
        work.loc[missing_mask, "name"] = fb_name
    # Standardize gender using provided Gender + Description + Name
    work["gender"] = [
        infer_gender(g, name_hint=n, desc_hint=d)
        for g, n, d in zip(work["Gender"], work["Name"], work["Description"])
    ]

    # Normalize accords and description
    work["main_accords"] = work["MainAccords"].astype(str).apply(normalize_accords)
    work["description"] = work["Description"].apply(one_liner)

    # Convert ratings (clip and fill)
    work["rating_value"] = pd.to_numeric(work["rating_value_raw"], errors="coerce").clip(0, 5).fillna(0.0)
    work["rating_count"] = pd.to_numeric(work["rating_count_raw"], errors="coerce").clip(lower=0).fillna(0).astype(int)

    # Generate PLN price ranges (stable RNG, mildly correlated with rating)
    rng = np.random.default_rng(2025)
    base_min = rng.integers(150, 900, size=len(work))  # 150–900 PLN
    # higher rated → gently higher chance for bigger range
    bonus = (work["rating_value"] - 3.5).clip(lower=0) * rng.integers(20, 80, size=len(work))
    work["price_min"] = (base_min + bonus).round().astype(int)
    work["price_max"] = (work["price_min"] + rng.integers(120, 700, size=len(work))).astype(int)

    # Longevity/Sillage 2–5 (biased a bit by rating)
    base_lon = rng.integers(2, 6, size=len(work))
    base_sil = rng.integers(2, 6, size=len(work))
    bias = np.where(work["rating_value"] >= 4.4, 1, 0)
    work["longevity"] = np.clip(base_lon + bias, 2, 5).astype(int)
    work["sillage"] = np.clip(base_sil + bias, 2, 5).astype(int)

    # Final selection & cleanup
    out = work[[
        "brand","name","gender",
        "price_min","price_max",
        "main_accords",
        "longevity","sillage",
        "description",
        "rating_value","rating_count",
        "URL"
    ]].rename(columns={"URL": "url"})

    # Drop obvious bad rows
    out = out.dropna(subset=["brand","name","main_accords"])
    out = out[out["brand"].astype(str).str.strip() != ""]
    out = out[out["name"].astype(str).str.strip() != ""]
    out = out[out["main_accords"].astype(str).str.strip() != ""]

    # Deduplicate by (brand, name)
    out = out.drop_duplicates(subset=["brand","name"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"✅ Saved: {OUT_PATH} | rows: {len(out)}")
    print(out.head(5).to_string())

if __name__ == "__main__":
    main()