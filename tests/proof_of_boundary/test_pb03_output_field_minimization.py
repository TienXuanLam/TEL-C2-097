# PB-03 (domain): S-2/S-3 sensitive-data minimization. The composed review
# packet must never echo denylisted sensitive field keys verbatim, and the
# minimization step must not false-positive on the agent's own generated
# Markdown headings/labels (PLAYBOOK A8 -- a bare "two capitalized words"
# regex always false-positives on headings like "Case Reference" or
# "Route Classification"; this template avoids that failure mode entirely
# by using an explicit sensitive-key denylist + regulated-data-value-shape
# redaction rather than a name-detection regex, but this test still proves
# real agent-generated headings survive untouched).

from src.services.report_composition_service import HumanHandoffStep


class TestOutputFieldMinimization:
    def test_sensitive_keys_are_stripped_from_reasons(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="missing_certification_evidence",
            route_reasons=[
                {
                    "field": "technician_certification_record",
                    "rule_id": "checklist:certification_record",
                    "original": "n/a",
                    "normalized": "n/a",
                    "reason": "Required document missing",
                    "national_id": "123-45-6789",
                    "date_of_birth": "1980-01-01",
                }
            ],
            target_queue="field-operations-certification-review",
            evidence_findings=[],
            source_references=[],
        )
        for reason in outcome["review_packet"]["reasons"]:
            assert "national_id" not in reason
            assert "date_of_birth" not in reason

    def test_sensitive_keys_are_stripped_from_evidence_findings(self):
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[
                {
                    "field": "certification_record",
                    "rule_id": "checklist:certification_record",
                    "status": "present",
                    "reason": "ok",
                    "source_ref": "doc-1",
                    "phone_number": "555-000-1111",
                }
            ],
            source_references=[],
        )
        for finding in outcome["review_packet"]["evidence_findings"]:
            assert "phone_number" not in finding

    def test_regulated_value_shapes_redacted_in_free_text_fields(self):
        """A key-only denylist does not protect a value that happens to
        land in an allow-listed field like `reason` — verify the value
        redaction closes that gap from the start."""
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-1",
            selected_route="human_field_operations_review",
            route_reasons=[
                {
                    "field": "overall_submission",
                    "rule_id": "route:human_field_operations_review_default",
                    "original": "n/a",
                    "normalized": "n/a",
                    "reason": "Contact technician at 555-123-4567 or tech@example.com",
                }
            ],
            target_queue="field-operations-site-authorisation-review",
            evidence_findings=[],
            source_references=[],
        )
        reason_text = outcome["review_packet"]["reasons"][0]["reason"]
        assert "555-123-4567" not in reason_text
        assert "tech@example.com" not in reason_text
        assert "[REDACTED]" in reason_text

    def test_own_generated_headings_are_not_treated_as_sensitive(self):
        """Regression per PLAYBOOK A8: the agent's own real Markdown headings
        ('Case Reference', 'Field-Level Reasons', 'Evidence Findings') must
        survive minimization untouched -- they are structural labels, not
        PII, and must never be redacted."""
        step = HumanHandoffStep()
        outcome = step.execute(
            case_reference="CASE-777",
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
                    "field": "site_access_authorisation_record",
                    "rule_id": "checklist:site_access_authorisation",
                    "status": "present",
                    "reason": "Document 'site_access_authorisation' submitted and readable",
                    "source_ref": "site_access_authorisation",
                }
            ],
            source_references=["doc-1"],
        )
        markdown = outcome["review_packet_markdown"]
        assert "# Field Technician Certification Access Evidence" in markdown
        assert "## Field-Level Reasons" in markdown
        assert "## Evidence Findings" in markdown
        assert "CASE-777" in markdown
