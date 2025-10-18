from __future__ import annotations

from typing import List, Set
import numpy as np
import pandas as pd

# simple rules to bias results by use-case
USECASE_RULES = {
    "office": {"boost": {"citrus","green","woody","fresh"}, "penalize": {"oud","amber","very_sweet"}},
    "date":   {"boost": {"amber","vanilla","spicy","sweet"},  "penalize": {"aquatic","green"}},
    "summer": {"boost": {"citrus","aquatic","green","fresh"}, "penalize": {"heavy","oud"}},
    "winter": {"boost": {"amber","vanilla","spicy","oud"},    "penalize": {"aquatic","citrus"}},
}

def accords_set(row: pd.Series) -> Set[str]:
    raw = (row.get("main_accords") or "")
    return set(str(raw).lower().split("|")) if raw else set()

def usecase_score(accords: Set[str], use_cases: List[str] | None) -> float:
    if not use_cases:
        return 0.5
    s = 0.0
    for uc in use_cases:
        rule = USECASE_RULES.get(uc, {"boost": set(), "penalize": set()})
        s += 0.5 + 0.1 * len(accords & rule["boost"]) - 0.05 * len(accords & rule["penalize"])
    return float(np.clip(s / len(use_cases), 0.0, 1.0))

def final_score(content_sim: float, uc: float, lon: float) -> float:
    # weights: 65% text similarity, 25% use-case fit, 10% longevity/sillage
    return 0.65 * content_sim + 0.25 * uc + 0.10 * lon