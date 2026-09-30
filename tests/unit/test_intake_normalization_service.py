from src.services.intake_normalization_service import SecureIntakeStep


class TestSecureIntakeStep:
    def test_valid_input_normalizes_successfully(self):
        step = SecureIntakeStep()
        outcome = step.execute(
            {
                "case_reference": " CASE-123 ",
                "technician_reference": "TECH-1",
                "site_reference": "SITE-9",
                "equipment_class": "fiber_splice",
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": True, "source_ref": "d1"}
                ],
                "source_references": ["d1"],
            }
        )
        assert outcome["errors"] == []
        assert outcome["case_reference"] == "CASE-123"
        assert outcome["normalized_case"]["equipment_class"] == "fiber_splice"

    def test_missing_case_reference_produces_error(self):
        step = SecureIntakeStep()
        outcome = step.execute({"technician_reference": "TECH-1"})
        assert any("case_reference" in e for e in outcome["errors"])

    def test_missing_technician_reference_produces_error(self):
        step = SecureIntakeStep()
        outcome = step.execute({"case_reference": "CASE-1"})
        assert any("technician_reference" in e for e in outcome["errors"])

    def test_original_and_normalized_values_both_preserved(self):
        """Proposal §11 Risk #2 mitigation: preserve original + normalized."""
        step = SecureIntakeStep()
        outcome = step.execute(
            {"case_reference": " CASE-1 ", "technician_reference": "TECH-1"}
        )
        cr = outcome["normalized_case"]["case_reference"]
        assert cr["original"] == " CASE-1 "
        assert cr["normalized"] == "CASE-1"

    def test_unreadable_document_marked_not_readable(self):
        step = SecureIntakeStep()
        outcome = step.execute(
            {
                "case_reference": "CASE-1",
                "technician_reference": "TECH-1",
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": False, "source_ref": "d1"}
                ],
            }
        )
        docs = outcome["normalized_case"]["evidence_documents"]
        assert docs[0]["readable"] is False

    def test_non_list_evidence_documents_defaults_to_empty(self):
        step = SecureIntakeStep()
        outcome = step.execute(
            {
                "case_reference": "CASE-1",
                "technician_reference": "TECH-1",
                "evidence_documents": "not-a-list",
            }
        )
        assert outcome["normalized_case"]["evidence_documents"] == []

    def test_normalized_case_json_round_trips(self):
        import json

        step = SecureIntakeStep()
        outcome = step.execute({"case_reference": "CASE-1", "technician_reference": "TECH-1"})
        parsed = json.loads(outcome["normalized_case_json"])
        assert parsed["case_reference"]["normalized"] == "CASE-1"
