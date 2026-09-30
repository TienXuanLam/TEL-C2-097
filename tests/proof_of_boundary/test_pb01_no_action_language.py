# PB-01 (domain): Advisory-only guarantee — no access-grant/scheduling/
# contact language in the composed review packet (proposal Risk #4: "A user
# interprets the route as a field operations or site-access-action
# decision").
#
# Regression test grounded in PLAYBOOK A8: exercise the REAL render service
# with realistic agent-generated headings/labels, not synthetic strings —
# this is the only way to catch a false-positive/false-negative in the
# forbidden-language scan against the agent's own actual output shape.

from src.services.report_composition_service import HumanHandoffStep


def _build_clean_packet():
    step = HumanHandoffStep()
    return step.execute(
        case_reference="CASE-1",
        selected_route="human_field_operations_review",
        route_reasons=[
            {
                "field": "overall_submission",
                "rule_id": "route:human_field_operations_review_default",
                "original": "n/a",
                "normalized": "n/a",
                "reason": "All evidence present and consistent",
            }
        ],
        target_queue="field-operations-site-authorisation-review",
        evidence_findings=[
            {
                "field": "technician_certification_record",
                "rule_id": "checklist:certification_record",
                "status": "present",
                "reason": "Document 'certification_record' submitted and readable",
                "source_ref": "certification_record",
            }
        ],
        source_references=["doc-1"],
    )


class TestAdvisoryOnlyGuarantee:
    def test_real_agent_output_passes_advisory_scan(self):
        """The agent's own real Markdown output (real headings like
        'Field-Level Reasons', 'Evidence Findings') must not itself trip the
        forbidden-language scan — this is the PB-01 regression target from
        PLAYBOOK A8."""
        outcome = _build_clean_packet()
        assert outcome["advisory_label_ok"] is True
        assert "ADVISORY ONLY" in outcome["review_packet_markdown"]

    def test_disclaimer_present_in_every_packet(self):
        outcome = _build_clean_packet()
        assert outcome["review_packet"]["advisory_only"] is True
        assert "does NOT constitute" in outcome["review_packet"]["disclaimer"]

    def test_forbidden_access_grant_language_is_detected(self):
        """A hypothetical packet that leaks access-grant language must fail
        the scan (proves the scan is not a no-op)."""
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[
                {
                    "field": "x",
                    "rule_id": "y",
                    "original": "a",
                    "normalized": "b",
                    "reason": "Access is granted and the technician has been dispatched",
                }
            ],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
        )
        assert outcome["advisory_label_ok"] is False

    def test_forbidden_scheduling_language_is_detected(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-2",
            selected_route="site_access_authorisation_review",
            route_reasons=[
                {
                    "field": "x",
                    "rule_id": "y",
                    "original": "a",
                    "normalized": "b",
                    "reason": "technician scheduled for dispatch tomorrow",
                }
            ],
            target_queue="field-operations-certification-review",
            evidence_findings=[],
            source_references=[],
        )
        assert outcome["advisory_label_ok"] is False
