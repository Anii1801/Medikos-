"""Small, honest baseline evaluation; no external data or model is assumed.

This measures policy invariants only. It is not a clinical accuracy study and
does not claim MediTOD or JEV performance.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.history_agent import HistoryTakingAgent


def run():
    cases = [
        [("cc", "Chest pain"), ("dur", "Today"), ("sev", "Severe"),
         ("cp_char", "Pressure / heaviness"), ("cp_rad", "Arm / jaw / back")],
        [("cc", "Fever"), ("dur", "Few days"), ("sev", "Moderate")],
        [("cc", "Headache"), ("dur", "Today"), ("sev", "Severe"),
         ("ha_type", "Sudden, worst ever")],
    ]
    duplicate_free = 0
    red_flag_cases = 0
    for case in cases:
        agent = HistoryTakingAgent()
        seen = []
        result = agent.next_response()
        for field, value in case:
            seen.append(result.question["id"])
            result = agent.answer(field, value)
        duplicate_free += int(len(seen) == len(set(seen)))
        red_flag_cases += int(bool(result.red_flags))
    print({
        "cases": len(cases),
        "duplicate_free_cases": duplicate_free,
        "duplicate_free_rate": duplicate_free / len(cases),
        "cases_with_expected_red_flags": red_flag_cases,
        "note": "Invariant smoke test; not clinical validation and no LLM was run.",
    })


if __name__ == "__main__":
    run()
