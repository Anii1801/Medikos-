"""Optional LLM layer. Active only when ANTHROPIC_API_KEY is set; otherwise everything works rule-based.
The LLM may only rephrase/organise patient-reported facts — never diagnose."""
import os, json, httpx

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SYSTEM = ("You convert a patient's self-reported intake into a concise physician-ready history. Use ONLY the facts provided. "
          "Do not diagnose, do not add facts, keep every section title. Return JSON: a list of {\"title\":str,\"text\":str}.")

def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))

def refine_sections(sections: list[dict]) -> list[dict] | None:
    if not enabled(): return None
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=30,
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 2000, "system": SYSTEM, "messages": [{"role": "user", "content": json.dumps(sections, ensure_ascii=False)}]})
        r.raise_for_status()
        txt = "".join(b.get("text", "") for b in r.json()["content"]).strip().strip("`")
        if txt.startswith("json"): txt = txt[4:]
        out = json.loads(txt)
        if isinstance(out, list) and {s["title"] for s in out} == {s["title"] for s in sections}:
            return out
    except Exception:
        return None
    return None
