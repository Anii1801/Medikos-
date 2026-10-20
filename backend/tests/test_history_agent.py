from app.history_agent import AdaptiveHistoryTakingAgent, HistoryTakingAgent


def test_stateful_questions_are_unique_and_persistable():
    agent = HistoryTakingAgent(budget=4)
    first = agent.next_response()
    second = agent.answer("cc", "Chest pain")
    third = agent.answer("dur", "Today")
    restored = HistoryTakingAgent.from_dict(agent.to_dict())
    assert first.question["id"] == "cc"
    assert second.question["id"] == "dur"
    assert third.question["id"] == "sev"
    assert restored.next_response().question["id"] == "sev"


def test_adaptive_contract_records_slot_provenance_and_attempts():
    agent = AdaptiveHistoryTakingAgent()
    agent.answer("cc", "Chest pain")
    agent.answer("cc", "Chest pain, still present")
    slot = agent.state["slot_state"]["cc"]
    assert slot["source"] == "patient"
    assert slot["provenance"]["source_type"] == "patient"
    assert slot["attempts"] == 2
    assert slot["last_attempt"] == 2


def test_negation_and_uncertainty_are_retained_without_inference():
    agent = HistoryTakingAgent()
    agent.answer("cc", "Chest pain")
    result = agent.answer("assoc", ["No sweating", "unsure about dizziness"])
    assert all(flag["code"] != "ACS" for flag in result.red_flags)
    assert "assoc" in result.uncertainty
    assert agent.state["answers"]["assoc"] == ["No sweating", "unsure about dizziness"]


def test_conflicting_answers_are_reported():
    agent = HistoryTakingAgent()
    agent.answer("cc", "Chest pain")
    agent.answer("dur", "Today")
    result = agent.answer("dur", "Months")
    assert "dur" in result.conflicts


def test_invalid_adapter_cannot_change_policy_question():
    class InvalidAdapter:
        name = "invalid"
        trained = True
        source = "test"

        def generate_question(self, **kwargs):
            return {"id": "different", "type": "text"}

    result = HistoryTakingAgent(adapter=InvalidAdapter()).next_response()
    assert result.question["id"] == "cc"

def test_confidence_aware_routing_escalates_uncertainty_and_keeps_safety_gate():
    agent = HistoryTakingAgent()
    result = agent.answer("cc", "Chest pain")
    assert result.decision_route == "adaptive_follow_up"
    result = agent.answer("dur", "I am unsure")
    assert result.review_required is True
    assert result.decision_route == "human_review"
    assert result.safety_validated is True

def test_red_flag_route_cannot_be_downgraded_by_confidence():
    agent = HistoryTakingAgent()
    result = agent.answer("cc", "Chest pain")
    result = agent.answer("cp_rad", "Arm / jaw / back")
    assert result.red_flags
    assert result.decision_route == "safety_review"
    assert result.review_required is True


def test_budget_is_a_safe_stopping_condition():
    agent = HistoryTakingAgent(budget=1)
    agent.next_response()
    result = agent.answer("cc", "Fever")
    assert result.complete is True
    assert result.question is None
