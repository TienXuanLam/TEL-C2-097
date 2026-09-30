import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.post_process_node import PostProcessNode


def _base_state(**overrides):
    state = {
        "case_reference": "CASE-1",
        "selected_route": "human_field_operations_review",
        "target_queue": "field-operations-site-authorisation-review",
        "route_reasons_json": json.dumps(
            [
                {
                    "field": "overall_submission",
                    "rule_id": "route:human_field_operations_review_default",
                    "original": "n/a",
                    "normalized": "n/a",
                    "reason": "All evidence present and consistent",
                }
            ]
        ),
        "evidence_findings_json": "[]",
        "normalized_case_json": json.dumps({"source_references": ["d1"]}),
        "config_unconfirmed": False,
        "node_history": [],
        "error_log": [],
    }
    state.update(overrides)
    return state


class TestPostProcessNode:
    def setup_method(self):
        self.node = PostProcessNode()

    def test_required_trust_level_is_verified_external(self):
        assert self.node.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_success_path_composes_advisory_packet(self):
        result = self.node.execute(_base_state())
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["advisory_label_ok"] is True
        assert result["formatted_output"]["advisory_only"] is True

    def test_extra_security_gate_output_blocks_non_advisory_packet(self):
        import pytest

        with pytest.raises(RuntimeError):
            self.node._extra_security_gate_output({"advisory_label_ok": False})

    def test_extra_security_gate_output_passes_advisory_packet(self):
        result = {"advisory_label_ok": True}
        gated = self.node._extra_security_gate_output(result)
        assert gated == result

    def test_missing_route_reasons_json_defaults_to_empty(self):
        state = _base_state(route_reasons_json=None)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value

    def test_config_unconfirmed_propagates_to_output_packet(self):
        state = _base_state(config_unconfirmed=True)
        result = self.node.execute(state)
        assert result["formatted_output"]["config_unconfirmed"] is True
