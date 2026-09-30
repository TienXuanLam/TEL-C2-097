import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.pre_process_node import PreProcessNode


class TestPreProcessNode:
    def setup_method(self):
        self.node = PreProcessNode()

    def test_required_trust_level_is_verified_external(self):
        assert self.node.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_success_path_normalizes_valid_request(self):
        state = {
            "user_input": json.dumps(
                {
                    "case_reference": "CASE-1",
                    "technician_reference": "TECH-1",
                    "site_reference": "SITE-1",
                    "equipment_class": "fiber_splice",
                    "evidence_documents": [],
                }
            ),
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["case_reference"] == "CASE-1"
        assert result["normalized_case_json"] is not None

    def test_missing_case_reference_returns_error(self):
        state = {
            "user_input": json.dumps({"technician_reference": "TECH-1"}),
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert len(result["error_log"]) > 0

    def test_extra_security_gate_input_rejects_empty_context(self):
        state = {"user_input": json.dumps({}), "node_history": [], "error_log": []}
        gated = self.node._extra_security_gate_input(state)
        assert gated["status"] == AgentStatus.ERROR.value

    def test_extra_security_gate_input_rejects_non_json_input(self):
        state = {"user_input": "not json", "node_history": [], "error_log": []}
        gated = self.node._extra_security_gate_input(state)
        assert gated["status"] == AgentStatus.ERROR.value

    def test_extra_security_gate_input_passes_valid_context(self):
        state = {
            "user_input": json.dumps({"case_reference": "CASE-1"}),
            "node_history": [],
            "error_log": [],
        }
        gated = self.node._extra_security_gate_input(state)
        assert gated.get("status") != AgentStatus.ERROR.value

    def test_short_circuits_execute_when_status_already_error(self):
        """If the S-2 hook already rejected, execute() must not attempt
        normalization again (defensive guard)."""
        state = {
            "user_input": json.dumps({}),
            "status": AgentStatus.ERROR.value,
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result == {}
