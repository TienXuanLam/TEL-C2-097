from src.services.report_composition_service import HumanHandoffStep


class TestHumanHandoffStep:
    def test_execute_returns_all_expected_keys(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
        )
        for key in (
            "review_packet",
            "review_packet_json",
            "review_packet_markdown",
            "advisory_label_ok",
        ):
            assert key in outcome

    def test_review_packet_json_round_trips(self):
        import json

        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="missing_certification_evidence",
            route_reasons=[],
            target_queue="field-operations-certification-review",
            evidence_findings=[],
            source_references=["src-1"],
        )
        parsed = json.loads(outcome["review_packet_json"])
        assert parsed["route"] == "missing_certification_evidence"
        assert parsed["target_queue"] == "field-operations-certification-review"
        assert parsed["source_references"] == ["src-1"]

    def test_advisory_only_flag_always_true_in_packet(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="duplicate_access_request_review",
            route_reasons=[],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
        )
        assert outcome["review_packet"]["advisory_only"] is True

    def test_config_unconfirmed_surfaced_in_packet(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
            config_unconfirmed=True,
        )
        assert outcome["review_packet"]["config_unconfirmed"] is True

    def test_config_unconfirmed_defaults_false(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
        )
        assert outcome["review_packet"]["config_unconfirmed"] is False
