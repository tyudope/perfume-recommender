import os, json, httpx
from typing import List, Dict, Any

# Read env at import-time (main.py already calls load_dotenv)
# Accept both naming conventions to avoid silent "unavailable" issues
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or ""
MODEL = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

def llm_available() -> bool:
    """Return True if a usable API key is present."""
    return bool(OPENAI_API_KEY)

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
            f"{i}. {c.get('brand','')} {c.get('name','')} | accords: {accords} | "
            f"price_range: {price_min}–{price_max} PLN"
        )
    lines += [
        "",
        'Return strict JSON exactly as: {"list":[{"bullets":["...","..."]}, ...]} (same order as candidates).'
    ]
    return "\n".join(lines)

def _openai_chat(prompt: str) -> str:
    """Call OpenAI chat completions and return the assistant content (JSON string)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("LLM key missing")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
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
        # Defensive: ensure expected shape
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        return content

def llm_explain(context: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[str]:
    """Return up to len(candidates) short explanations (bulleted) aligned to candidates order."""
    if not llm_available() or not candidates:
        return []
    try:
        # Build prompt for only the slice main.py asked for
        prompt = build_prompt(context, candidates)
        raw = _openai_chat(prompt)
        obj = json.loads(raw)
        items = obj.get("list") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            return []

        outs: List[str] = []
        for i in range(len(candidates)):
            try:
                bullets = items[i].get("bullets", [])
                # keep max 2 bullets, each trimmed
                outs.append("\n".join(f"• {str(b).strip()}" for b in bullets[:2] if str(b).strip()))
            except Exception:
                outs.append("")
        return outs
    except Exception as e:
        # Don't crash the request if LLM fails
        print("LLM error:", repr(e))
        return []