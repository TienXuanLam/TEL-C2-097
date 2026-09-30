# TC-08: required_trust_level declared and enforced.
#
# Per the TC-08 review criterion, dedicated S-1 boundary
# coverage MUST call node(state) (via __call__), not node.execute(state),
# to prove execute() is never reached when the caller's trust level is
# insufficient.

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.main_node import MainNode
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode

ALL_NODE_CLASSES = [PreProcessNode, MainNode, PostProcessNode]


class TestTrustGateEnforcement:
    def test_all_nodes_declare_verified_external_explicitly(self):
        for node_cls in ALL_NODE_CLASSES:
            assert node_cls.required_trust_level == TrustLevel.VERIFIED_EXTERNAL, (
                f"{node_cls.__name__} must explicitly declare "
                "required_trust_level = TrustLevel.VERIFIED_EXTERNAL"
            )

    def test_anonymous_caller_blocked_before_execute(self, monkeypatch):
        for node_cls in ALL_NODE_CLASSES:
            node = node_cls()
            execute_called = {"flag": False}

            def spy_execute(self, state, _flag=execute_called):
                _flag["flag"] = True
                return {"status": AgentStatus.SUCCESS.value}

            monkeypatch.setattr(node_cls, "execute", spy_execute)

            state = {
                "caller_trust_level": TrustLevel.ANONYMOUS.value,
                "correlation_id": "trust-gate-test",
                "node_history": [],
                "error_log": [],
            }
            result = node(state)  # via __call__, not execute() directly

            assert result["status"] == AgentStatus.ERROR.value, node_cls.__name__
            assert execute_called["flag"] is False, (
                f"{node_cls.__name__}.execute() must NOT be called when "
                "caller_trust_level is below required_trust_level"
            )

    def test_verified_external_caller_allowed(self, monkeypatch):
        for node_cls in ALL_NODE_CLASSES:
            node = node_cls()
            execute_called = {"flag": False}

            def spy_execute(self, state, _flag=execute_called):
                _flag["flag"] = True
                return {"status": AgentStatus.SUCCESS.value}

            monkeypatch.setattr(node_cls, "execute", spy_execute)

            state = {
                "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
                "correlation_id": "trust-gate-test",
                "node_history": [],
                "error_log": [],
                # PreProcessNode's S-2 hook rejects an empty user_input
                # before execute() runs — supply a minimal valid manifest so
                # this generic trust-gate test reaches execute() for every
                # node class, not just nodes without a domain input gate.
                "user_input": '{"case_reference": "TRUST-TEST", "technician_reference": "TECH-TRUST"}',
            }
            node(state)

            assert execute_called["flag"] is True, node_cls.__name__
