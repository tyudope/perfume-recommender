import os, json, httpx
from typing import List, Dict, Any

# read env at import-time (safe because main.py calls load_dotenv first)
PROVIDER = os.getenv("PROVIDER", "openai").lower()
LLM_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

def llm_available() -> bool:
    return bool(LLM_KEY)

def build_prompt(context: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    liked = ", ".join(context.get("liked") or [])
    use_cases = ", ".join(context.get("use_cases") or [])
    notes = ", ".join(context.get("preferred_notes") or [])
    budget = context.get("budget", "unspecified")

    lines = [
        "You are a professional fragrance consultant.",
        "For EACH candidate, write 2 short bullet points (<= 18 words each).",
        "Be specific and grounded in given accords & price range. Mention use-case fit (office/date/summer/winter) and budget fit if relevant.",
        "You MAY compare to the user's liked perfumes, but do not invent new notes or prices.",
        "",
        f"User liked: {liked or '—'}",
        f"Use-cases: {use_cases or '—'}",
        f"Preferred notes: {notes or '—'}",
        f"Budget: {budget}",
        "",
        "Candidates (use ONLY this data):",
    ]
    for i, c in enumerate(candidates, 1):
        accords = ", ".join(c.get("accords") or [])
        price_min, price_max = (c.get("price_range") or [None, None])
        lines.append(
            f"{i}. {c.get('brand','')} {c.get('name','')} | accords: {accords} | price_range: {price_min}–{price_max} PLN"
        )
    lines += [
        "",
        'Return strict JSON exactly as: {"list":[{"bullets":["...","..."]}, ...]} (same order as candidates).'
    ]
    return "\n".join(lines)

def _openai_chat(prompt: str) -> str:
    if not LLM_KEY:
        raise RuntimeError("LLM key missing")
    headers = {"Authorization": f"Bearer {LLM_KEY}"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise expert on fragrances."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}  # ask for JSON
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{OPENAI_BASE}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

def llm_explain(context: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[str]:
    if not llm_available() or not candidates:
        return []
    try:
        raw = _openai_chat(build_prompt(context, candidates))
        obj = json.loads(raw)
        items = obj.get("list") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            return []
        outs = []
        for i in range(len(candidates)):
            try:
                bullets = items[i].get("bullets", [])
                outs.append("\n".join(f"• {b.strip()}" for b in bullets[:2] if str(b).strip()))
            except Exception:
                outs.append("")
        return outs
    except Exception as e:
        print("LLM error:", repr(e))
        return []