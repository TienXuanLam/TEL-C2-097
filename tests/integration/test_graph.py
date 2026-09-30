# TEL-C2-097 — Integration test: full graph compile + invoke.

import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.graph import TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent


def _clean_case_manifest():
    return {
        "case_reference": "CASE-123456",
        "technician_reference": "TECH-1",
        "site_reference": "SITE-9",
        "equipment_class": "fiber_splice",
        "evidence_documents": [
            {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
            {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
        ],
        "requirement_window": {},
        "source_references": ["d1", "d2"],
    }


_FULL_CONFIG = {
    "checklist": [
        {
            "field": "technician_certification_record",
            "doc_type": "certification_record",
            "category": "certification",
            "rule_id": "checklist:certification_record",
            "required": True,
        },
        {
            "field": "site_access_authorisation_record",
            "doc_type": "site_access_authorisation",
            "category": "site_access",
            "rule_id": "checklist:site_access_authorisation",
            "required": True,
        },
    ],
    "qualification_index": {"CASE-123456": True},
    "qualification_expiry_rules": {
        "min_days_before_today": -30,
        "max_days_after_today": 180,
    },
    "duplicate_request_index": [],
}


class TestFullPipeline:
    def setup_method(self):
        self.agent = TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent()
        self.agent.compile()

    def _invoke(self, agent, manifest, session_id="itest", trust=TrustLevel.VERIFIED_EXTERNAL):
        with bound_secrets(InMemoryProvider({})):
            ctx = InvocationContext(
                session_id=session_id,
                caller_trust_level=trust,
                caller_id="field-ops-user",
            )
            return agent.invoke(json.dumps(manifest), ctx=ctx)

    def test_full_pipeline_success_clean_submission(self):
        result = self._invoke(self.agent, _clean_case_manifest(), "itest-1")

        assert result["status"] == "success"
        assert result["output"] is not None
        assert result["output"]["route"] == "human_field_operations_review"
        assert result["output"]["target_queue"] == "field-operations-site-authorisation-review"
        assert result["output"]["advisory_only"] is True
        assert "node_history" in result
        for expected_node in (
            "InitializeNode",
            "PreProcessNode",
            "MainNode",
            "PostProcessNode",
            "FinalizeNode",
        ):
            assert expected_node in result["node_history"]

    def test_full_pipeline_missing_certification_document(self):
        manifest = _clean_case_manifest()
        manifest["evidence_documents"] = [
            {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"}
        ]
        result = self._invoke(self.agent, manifest, "itest-2")

        assert result["status"] == "success"
        assert result["output"]["route"] == "missing_certification_evidence"
        assert result["output"]["target_queue"] == "field-operations-certification-review"

    def test_full_pipeline_missing_site_access_document(self):
        """Graph-level coverage for site_access_authorisation_review —
        certification evidence present, site_access_authorisation missing,
        so certification checks pass but a site_access checklist item does
        not."""
        manifest = _clean_case_manifest()
        manifest["evidence_documents"] = [
            {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
        ]
        result = self._invoke(self.agent, manifest, "itest-3")

        assert result["status"] == "success"
        assert result["output"]["route"] == "site_access_authorisation_review"
        assert result["output"]["target_queue"] == "field-operations-certification-review"

    def test_full_pipeline_qualification_expiry_conflict(self):
        agent = TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent(config=_FULL_CONFIG)
        agent.compile()
        manifest = _clean_case_manifest()
        manifest["requirement_window"] = {"effective_date": "2099-01-01"}
        result = self._invoke(agent, manifest, "itest-4")

        assert result["status"] == "success"
        assert result["output"]["route"] == "qualification_expiry_conflict_review"
        assert result["output"]["target_queue"] == "field-operations-site-authorisation-review"
        assert result["output"]["config_unconfirmed"] is False

    def test_full_pipeline_duplicate_access_request(self):
        """Graph-level coverage for duplicate_access_request_review —
        requires an agent instance with an injected duplicate_request_index
        (config_unconfirmed must be False here so the duplicate route, not
        the config-unconfirmed catch-all path, is what's exercised)."""
        config = dict(_FULL_CONFIG)
        config["duplicate_request_index"] = [
            {
                "technician_reference": "TECH-1",
                "site_reference": "SITE-9",
                "equipment_class": "fiber_splice",
            }
        ]
        agent = TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent(config=config)
        agent.compile()
        result = self._invoke(agent, _clean_case_manifest(), "itest-5")

        assert result["status"] == "success"
        assert result["output"]["route"] == "duplicate_access_request_review"
        assert result["output"]["target_queue"] == "field-operations-site-authorisation-review"
        assert result["output"]["config_unconfirmed"] is False

    def test_anonymous_caller_blocked_by_trust_gate(self):
        result = self._invoke(
            self.agent, _clean_case_manifest(), "itest-6", trust=TrustLevel.ANONYMOUS
        )
        assert result["status"] == "error"

    def test_empty_case_manifest_produces_error(self):
        result = self._invoke(self.agent, {}, "itest-7")
        assert result["status"] in ("error", "retry")

    def test_full_pipeline_unconfigured_dependencies_surface_warning(self):
        """Graph-level proof that a default-config agent (the one used by
        every other test in this file except the ones with explicit
        config) marks its output as config_unconfirmed, so no consumer can
        mistake it for a verified production routing decision."""
        result = self._invoke(self.agent, _clean_case_manifest(), "itest-8")

        assert result["output"]["config_unconfirmed"] is True
        assert any(
            r["rule_id"] == "config:unconfirmed_dependency"
            for r in result["output"]["reasons"]
        )

    def test_full_pipeline_s3_blocks_forbidden_language_end_to_end(self, monkeypatch):
        """The S-3 rejection path must be proven through the real
        __call__/graph invocation boundary, not only via a direct unit call
        to _extra_security_gate_output(). Monkeypatches the
        route-classification reason text to inject forbidden language, then
        asserts the graph-level invoke() surfaces a safe error result —
        never the unsafe packet."""
        import src.services.consistency_validation_service as consistency_module

        original_classify = consistency_module.RouteClassificationStep.classify

        def _poisoned_classify(self, *args, **kwargs):
            result = original_classify(self, *args, **kwargs)
            for reason in result["route_reasons"]:
                reason["reason"] = "Access is granted and the technician has been dispatched."
            result["route_reasons_json"] = json.dumps(result["route_reasons"])
            return result

        monkeypatch.setattr(
            consistency_module.RouteClassificationStep, "classify", _poisoned_classify
        )

        result = self._invoke(self.agent, _clean_case_manifest(), "itest-9")

        assert result["status"] == "error"
        assert result["output"] is None
