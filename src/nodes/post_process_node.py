"""AgentCore Platform v1.0"""

# Step mapping (docs/02_design.md "Architecture Overview"):
#   post_process (this FunctionNode) -> HumanHandoffStep (Step 4) execute()

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.report_composition_service import HumanHandoffStep


class PostProcessNode(FunctionNode):
    """Human Handoff — cited advisory result + target queue (proposal §4 Step 4)."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self) -> None:
        self._handoff_step = HumanHandoffStep()

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain hook: block output entirely if the advisory-only
        guarantee failed (proposal Risk #4 — forbidden access/scheduling/
        contact language detected). May raise — this is a legitimate
        block, not a redaction."""
        if result.get("advisory_label_ok") is False:
            raise RuntimeError(
                "S-3: review packet failed advisory-only validation "
                "(forbidden access-grant/scheduling/contact language detected)"
            )
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        case_reference = state.get("case_reference", "")
        selected_route = state.get("selected_route", "")
        target_queue = state.get("target_queue", "")
        route_reasons = json.loads(state.get("route_reasons_json") or "[]")
        evidence_findings = json.loads(state.get("evidence_findings_json") or "[]")
        normalized_case = json.loads(state.get("normalized_case_json") or "{}")
        source_references = normalized_case.get("source_references", [])

        outcome = self._handoff_step.execute(
            case_reference=case_reference,
            selected_route=selected_route,
            route_reasons=route_reasons,
            target_queue=target_queue,
            evidence_findings=evidence_findings,
            source_references=source_references,
            config_unconfirmed=bool(state.get("config_unconfirmed", False)),
        )

        emit_trace_event(
            "human_handoff_packet_composed",
            {
                "case_reference": case_reference,
                "target_queue": target_queue,
                "advisory_label_ok": outcome["advisory_label_ok"],
            },
            state,
        )

        return {
            "review_packet_json": outcome["review_packet_json"],
            "advisory_label_ok": outcome["advisory_label_ok"],
            "formatted_output": outcome["review_packet"],
            "status": AgentStatus.SUCCESS.value,
        }
