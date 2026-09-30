import inspect
import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.main_node import MainNode


def _normalized_case_json(**overrides):
    payload = {
        "case_reference": {"original": "CASE-1", "normalized": "CASE-1"},
        "technician_reference": {"original": "TECH-1", "normalized": "TECH-1"},
        "site_reference": {"original": "SITE-1", "normalized": "SITE-1"},
        "equipment_class": "fiber_splice",
        "evidence_documents": [
            {"doc_type": "certification_record", "readable": True, "source_ref": "d1"},
            {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"},
        ],
        "requirement_window": {},
        "source_references": ["d1", "d2"],
    }
    payload.update(overrides)
    return json.dumps(payload)


class TestMainNode:
    """Unit tests for the Certification Check + Route Classification node."""

    def setup_method(self):
        self.node = MainNode()

    def test_required_trust_level_is_verified_external(self):
        assert self.node.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_success_path_clean_submission_routes_human_field_operations_review(self):
        state = {
            "normalized_case_json": _normalized_case_json(),
            "case_reference": "CASE-1",
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert isinstance(result["status"], str)
        assert result["selected_route"] == "human_field_operations_review"
        assert result["target_queue"] == "field-operations-site-authorisation-review"

    def test_missing_normalized_case_json_returns_error(self):
        state = {"node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert len(result["error_log"]) > 0

    def test_missing_certification_document_routes_correctly(self):
        state = {
            "normalized_case_json": _normalized_case_json(
                evidence_documents=[
                    {"doc_type": "site_access_authorisation", "readable": True, "source_ref": "d2"}
                ]
            ),
            "case_reference": "CASE-1",
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["selected_route"] == "missing_certification_evidence"
        assert result["target_queue"] == "field-operations-certification-review"

    def test_config_unconfirmed_true_by_default(self):
        state = {
            "normalized_case_json": _normalized_case_json(),
            "case_reference": "CASE-1",
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["config_unconfirmed"] is True

    def test_execute_method_signature(self):
        """Node must implement execute(state) not _invoke_impl.

        Canonical contract (framework node-implementation review criterion):
          - Override: execute(self, state: AgentState) -> dict
          - PROHIBITED: _invoke_impl(), process() override
        """
        assert hasattr(MainNode, "execute"), "MainNode must implement execute()"

        sig = inspect.signature(MainNode.execute)
        params = list(sig.parameters.keys())
        assert len(params) >= 2, f"execute() must accept (self, state), got params: {params}"
        assert params[1] == "state", f"Second parameter must be 'state', got '{params[1]}'"
        assert "_invoke_impl" not in MainNode.__dict__, (
            "_invoke_impl() must not be defined in MainNode — use execute() instead"
        )

    def test_all_four_constructor_dependencies_accepted(self):
        """A6 wiring checklist: MainNode must accept all four config-provided
        dependencies (checklist / qualification_index /
        qualification_expiry_rules / duplicate_request_index) — verified
        here at the constructor-signature level; the real
        wiring-through-graph.py bug is caught by the e2e test, not this
        isolated unit test."""
        node = MainNode(
            checklist=[],
            qualification_index={},
            qualification_expiry_rules={"min_days_before_today": -1, "max_days_after_today": 1},
            duplicate_request_index=[],
        )
        assert node is not None
