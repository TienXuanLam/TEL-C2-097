# PB-02 (domain): Route classification MUST be deterministic — no `llm`
# parameter anywhere in the classify() signature. Any severity/threshold/
# escalation-trigger decision (here: which of the 5 routes applies) must be
# deterministic per EngineerGuide/IMPLEMENTATION_LOG.md A4; LLM use, if any,
# is reserved for narrative/rationale text only, never the routing decision.

import inspect

from src.services.consistency_validation_service import RouteClassificationStep


class TestDeterministicRouting:
    def test_classify_signature_has_no_llm_parameter(self):
        sig = inspect.signature(RouteClassificationStep.classify)
        assert "llm" not in sig.parameters, (
            "RouteClassificationStep.classify() must not accept an `llm` "
            "parameter — routing decisions must be deterministic"
        )

    def test_init_signature_has_no_llm_parameter(self):
        sig = inspect.signature(RouteClassificationStep.__init__)
        assert "llm" not in sig.parameters

    def test_classify_is_deterministic_across_repeated_calls(self):
        """Same inputs -> same route, every time (no hidden randomness)."""
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        kwargs = dict(
            case_reference="CASE-1",
            technician_reference="TECH-1",
            site_reference="SITE-1",
            equipment_class="fiber_splice",
            requirement_window={},
            missing_certification_fields=[],
            missing_site_access_fields=[],
        )
        results = {step.classify(**kwargs)["selected_route"] for _ in range(20)}
        assert results == {"human_field_operations_review"}

    def test_missing_certification_takes_precedence_over_site_access(self):
        step = RouteClassificationStep()
        result = step.classify(
            case_reference="CASE-1",
            technician_reference="TECH-1",
            site_reference="SITE-1",
            equipment_class="fiber_splice",
            requirement_window={},
            missing_certification_fields=[
                {"field": "a", "rule_id": "r1", "status": "missing", "reason": "x", "source_ref": "s"}
            ],
            missing_site_access_fields=[
                {"field": "b", "rule_id": "r2", "status": "missing", "reason": "y", "source_ref": "s2"}
            ],
        )
        assert result["selected_route"] == "missing_certification_evidence"
        assert result["target_queue"] == "field-operations-certification-review"

    def test_duplicate_detection_only_fires_when_evidence_complete(self):
        step = RouteClassificationStep(
            duplicate_request_index=[
                {"technician_reference": "TECH-DUP", "site_reference": "SITE-1", "equipment_class": "fiber_splice"}
            ]
        )
        result = step.classify(
            case_reference="CASE-1",
            technician_reference="TECH-DUP",
            site_reference="SITE-1",
            equipment_class="fiber_splice",
            requirement_window={},
            missing_certification_fields=[],
            missing_site_access_fields=[],
        )
        assert result["selected_route"] == "duplicate_access_request_review"
        assert result["target_queue"] == "field-operations-site-authorisation-review"
