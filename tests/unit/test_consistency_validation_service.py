from src.services.consistency_validation_service import (
    QUEUE_CERTIFICATION_REVIEW,
    QUEUE_SITE_AUTHORISATION_REVIEW,
    ROUTE_DUPLICATE_ACCESS_REQUEST,
    ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW,
    ROUTE_MISSING_CERTIFICATION,
    ROUTE_QUALIFICATION_EXPIRY_CONFLICT,
    ROUTE_SITE_ACCESS_AUTHORISATION_REVIEW,
    RouteClassificationStep,
)


def _classify(step, **overrides):
    kwargs = dict(
        case_reference="CASE-1",
        technician_reference="TECH-1",
        site_reference="SITE-1",
        equipment_class="fiber_splice",
        requirement_window={},
        missing_certification_fields=[],
        missing_site_access_fields=[],
    )
    kwargs.update(overrides)
    return step.classify(**kwargs)


class TestRouteClassificationStep:
    def test_clean_submission_routes_to_human_field_operations_review(self):
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        result = _classify(step)
        assert result["selected_route"] == ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW
        assert result["target_queue"] == QUEUE_SITE_AUTHORISATION_REVIEW

    def test_missing_certification_routes_correctly(self):
        step = RouteClassificationStep()
        result = _classify(
            step,
            missing_certification_fields=[
                {"field": "a", "rule_id": "r", "status": "missing", "reason": "y", "source_ref": "s"}
            ],
        )
        assert result["selected_route"] == ROUTE_MISSING_CERTIFICATION
        assert result["target_queue"] == QUEUE_CERTIFICATION_REVIEW

    def test_missing_site_access_routes_correctly(self):
        step = RouteClassificationStep()
        result = _classify(
            step,
            missing_site_access_fields=[
                {"field": "b", "rule_id": "r", "status": "missing", "reason": "y", "source_ref": "s"}
            ],
        )
        assert result["selected_route"] == ROUTE_SITE_ACCESS_AUTHORISATION_REVIEW
        assert result["target_queue"] == QUEUE_CERTIFICATION_REVIEW

    def test_expiry_conflict_routes_correctly(self):
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        result = _classify(step, requirement_window={"effective_date": "2099-01-01"})
        assert result["selected_route"] == ROUTE_QUALIFICATION_EXPIRY_CONFLICT
        assert result["target_queue"] == QUEUE_SITE_AUTHORISATION_REVIEW

    def test_unparsable_expiry_date_routes_to_conflict_review(self):
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        result = _classify(step, requirement_window={"effective_date": "not-a-date"})
        assert result["selected_route"] == ROUTE_QUALIFICATION_EXPIRY_CONFLICT

    def test_no_requirement_window_does_not_trigger_expiry_conflict(self):
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        result = _classify(step, requirement_window={})
        assert result["selected_route"] == ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW

    def test_duplicate_detected_when_evidence_and_expiry_are_clean(self):
        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[
                {"technician_reference": "TECH-1", "site_reference": "SITE-1", "equipment_class": "fiber_splice"}
            ],
        )
        result = _classify(step)
        assert result["selected_route"] == ROUTE_DUPLICATE_ACCESS_REQUEST
        assert result["target_queue"] == QUEUE_SITE_AUTHORISATION_REVIEW

    def test_missing_evidence_takes_precedence_over_duplicate(self):
        """Precedence order per docs/02_design.md ASSUMPTION callout: evidence
        completeness (1-2) is checked before duplicate detection (4)."""
        step = RouteClassificationStep(
            duplicate_request_index=[
                {"technician_reference": "TECH-1", "site_reference": "SITE-1", "equipment_class": "fiber_splice"}
            ],
        )
        result = _classify(
            step,
            missing_certification_fields=[
                {"field": "a", "rule_id": "r", "status": "missing", "reason": "y", "source_ref": "s"}
            ],
        )
        assert result["selected_route"] == ROUTE_MISSING_CERTIFICATION

    def test_route_reasons_json_round_trips(self):
        import json

        step = RouteClassificationStep(
            qualification_expiry_rules={"min_days_before_today": -30, "max_days_after_today": 180},
            duplicate_request_index=[],
        )
        result = _classify(step)
        parsed = json.loads(result["route_reasons_json"])
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert result["config_unconfirmed"] is False

    def test_config_unconfirmed_adds_warning_reason(self):
        """RouteClassificationStep() with no injected config must surface
        config_unconfirmed=True and prepend the warning reason."""
        step = RouteClassificationStep()
        result = _classify(step)
        assert result["config_unconfirmed"] is True
        reasons = result["route_reasons"]
        assert reasons[0]["rule_id"] == "config:unconfirmed_dependency"

    def test_classify_signature_has_no_llm_parameter(self):
        import inspect

        sig = inspect.signature(RouteClassificationStep.classify)
        assert "llm" not in sig.parameters
