"""Optional LLM wording layer (Gemini REST API). Disabled unless LLM_PROVIDER=gemini and GEMINI_API_KEY is set.

Safety: only aggregate, anonymised recommendation text is sent (no customer ids). The model may only rephrase;
scores, priorities, categories and evidence are never taken from its output. Any failure silently keeps the
deterministic text."""
from __future__ import annotations

import json

import pandas as pd
import requests

from config.logging_config import get_logger
from config.settings import settings

log = get_logger(__name__)


def llm_available() -> bool:
    return settings.llm_provider == "gemini" and bool(settings.gemini_api_key)


def enhance_recommendations(recs: pd.DataFrame) -> pd.DataFrame:
    if recs is None or recs.empty or not llm_available():
        return recs
    payload = [{"i": int(i), "problem": r["problem"], "action": r["suggested_action"], "impact": r["expected_impact"]}
               for i, r in recs.iterrows()]
    prompt = ("You edit business recommendations. Rewrite each item's 'action' and 'impact' in clear, professional, concise "
              "English. STRICT RULES: do not add facts, numbers, percentages or promises that are not in the input; keep "
              "every number unchanged; keep the 'directional - not a forecast' caveat. Return ONLY a JSON array of "
              "objects {\"i\", \"action\", \"impact\"}.\n\n" + json.dumps(payload))
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
            headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}},
            timeout=settings.http_timeout * 2,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        items = json.loads(text)
        out = recs.copy()
        for it in items:
            i = int(it["i"])
            if i in out.index and it.get("action") and it.get("impact"):
                out.at[i, "suggested_action"], out.at[i, "expected_impact"] = str(it["action"]), str(it["impact"])
                out.at[i, "llm_enhanced"] = True
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM enhancement skipped: %s", exc)
        return recs
