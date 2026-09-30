from src.services.evidence_mapping_service import CertificationCheckStep


class TestCertificationCheckStep:
    def test_all_documents_present_produces_no_missing_fields(self):
        step = CertificationCheckStep()
        outcome = step.execute(
            case_reference="CASE-1",
            normalized_case={
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
                    {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
                ]
            },
        )
        assert outcome["missing_certification_fields"] == []
        assert outcome["missing_site_access_fields"] == []

    def test_missing_certification_document_is_categorized_correctly(self):
        step = CertificationCheckStep()
        outcome = step.execute(
            case_reference="CASE-1",
            normalized_case={
                "evidence_documents": [
                    {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
                ]
            },
        )
        assert len(outcome["missing_certification_fields"]) == 1
        assert outcome["missing_site_access_fields"] == []

    def test_missing_site_access_document_is_categorized_correctly(self):
        step = CertificationCheckStep()
        outcome = step.execute(
            case_reference="CASE-1",
            normalized_case={
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
                ]
            },
        )
        assert outcome["missing_certification_fields"] == []
        assert len(outcome["missing_site_access_fields"]) == 1

    def test_unreadable_document_produces_evidence_insufficient_finding(self):
        """Proposal §11 Risk #1: unreadable document -> evidence-insufficient
        with source reference, not an inferred value."""
        step = CertificationCheckStep()
        outcome = step.execute(
            case_reference="CASE-1",
            normalized_case={
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": False, "source_ref": "d1"},
                    {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
                ]
            },
        )
        insufficient = [
            f for f in outcome["findings"] if f["status"] == "evidence_insufficient"
        ]
        assert len(insufficient) == 1
        assert insufficient[0]["source_ref"] == "certification_record"

    def test_qualification_index_cross_check(self):
        step = CertificationCheckStep(qualification_index={"CASE-1": False})
        outcome = step.execute(
            case_reference="CASE-1",
            normalized_case={
                "evidence_documents": [
                    {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
                    {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
                ]
            },
        )
        assert any(
            f["field"] == "qualification_record"
            for f in outcome["missing_certification_fields"]
        )

    def test_findings_json_round_trips(self):
        import json

        step = CertificationCheckStep()
        outcome = step.execute(case_reference="CASE-1", normalized_case={})
        parsed = json.loads(outcome["evidence_findings_json"])
        assert isinstance(parsed, list)

    def test_config_unconfirmed_true_when_no_config_injected(self):
        step = CertificationCheckStep()
        assert step.config_unconfirmed is True

    def test_config_unconfirmed_false_when_both_configs_injected(self):
        step = CertificationCheckStep(checklist=[], qualification_index={})
        assert step.config_unconfirmed is False

    def test_config_unconfirmed_true_when_only_one_config_injected(self):
        step = CertificationCheckStep(checklist=[])
        assert step.config_unconfirmed is True
