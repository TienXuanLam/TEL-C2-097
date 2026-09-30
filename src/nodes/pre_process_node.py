"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value strings for status assignments [A1]
#  - Never import from mediator/, api/, or other agents
#
# Step mapping (docs/02_design.md "Architecture Overview"):
#   pre_process (this FunctionNode) -> SecureIntakeStep (Step 1) execute()
#
# The HTTP entry point (src/api/server.py) only forwards a single `input`
# string to agent.invoke() — there is no separate input_context channel on
# the real /invoke contract (InvokeRequest.input: str, forwarded as
# agent.invoke(req.input, ctx=ctx), which becomes state["user_input"]). The
# caller-supplied case manifest therefore arrives as a JSON-encoded object
# string in state["user_input"] — this node parses it with json.loads(),
# never state.get("input_context", {}).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.intake_normalization_service import SecureIntakeStep


class PreProcessNode(FunctionNode):
    """Secure Intake — validate and normalize inputs (proposal §4 Step 1).

    S-1: caller must be an authorised telecom field-operations user, not
    anonymous — VERIFIED_EXTERNAL is required explicitly (not inherited
    implicitly from the ANONYMOUS default).
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self) -> None:
        self._intake_step = SecureIntakeStep()

    @staticmethod
    def _parse_input_context(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        try:
            parsed = json.loads(user_input) if isinstance(user_input, str) else user_input
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain hook: reject requests with no case manifest at all
        before normalization runs. Must not raise — set ERROR status."""
        input_context = self._parse_input_context(state)
        if not input_context:
            state = dict(state)
            state["status"] = AgentStatus.ERROR.value
            state["error_log"] = ["PreProcessNode: user_input is empty, not valid JSON, or not a JSON object"]
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("status") == AgentStatus.ERROR.value:
            # Rejected by S-2 hook already.
            return {}

        input_context = self._parse_input_context(state)

        outcome = self._intake_step.execute(input_context)

        emit_trace_event(
            "intake_normalization_completed",
            {
                "case_reference": outcome["case_reference"],
                "validation_error_count": len(outcome["errors"]),
            },
            state,
        )

        if outcome["errors"]:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"PreProcessNode: {e}" for e in outcome["errors"]],
                "input_validation_errors": outcome["errors"],
            }

        return {
            "normalized_case_json": outcome["normalized_case_json"],
            "case_reference": outcome["case_reference"],
            "input_validation_errors": [],
            "status": AgentStatus.SUCCESS.value,
        }
