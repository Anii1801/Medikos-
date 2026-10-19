"""Print a deterministic, reproducible adaptive interview demonstration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.history_agent import HistoryTakingAgent


def main():
    agent = HistoryTakingAgent(budget=8)
    response = agent.next_response()
    print(response.model_dump_json(indent=2))
    for field, value in (
        ("cc", "Chest pain"),
        ("dur", "Today"),
        ("sev", "Severe"),
        ("cp_char", "Pressure / heaviness"),
        ("cp_rad", "Arm / jaw / back"),
        ("cp_agg", "Worse on walking / effort"),
        ("assoc", ["No sweating", "unsure about dizziness"]),
    ):
        response = agent.answer(field, value)
        print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
