"""AgentCore Platform v1.0"""

# Step mapping (docs/02_design.md "Architecture Overview"):
#   main (this FunctionNode) -> CertificationCheckStep (Step 2) execute()
#                             -> RouteClassificationStep (Step 3) classify()
#
# Route classification (classify()) is deterministic — no `llm` parameter on
# its signature. See tests/proof_of_boundary/test_pb02_deterministic_domain_logic.py.

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.consistency_validation_service import RouteClassificationStep
from src.services.evidence_mapping_service import CertificationCheckStep


class MainNode(FunctionNode):
    """Certification Check + Route Classification (proposal §4 Steps 2-3)."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(
        self,
        checklist: list[dict[str, Any]] | None = None,
        qualification_index: dict[str, Any] | None = None,
        qualification_expiry_rules: dict[str, Any] | None = None,
        duplicate_request_index: list[dict[str, Any]] | None = None,
    ) -> None:
        # graph.py's register_nodes() MUST pass all four config-provided
        # dependencies here (checklist / qualification_index /
        # qualification_expiry_rules / duplicate_request_index) — this is
        # the single most common real bug in past implementations (a
        # related prior template had missing dependency wiring); verified
        # by a real e2e agent.invoke() test, not just isolated unit tests.
        self._certification_step = CertificationCheckStep(
            checklist=checklist,
            qualification_index=qualification_index,
        )
        self._route_step = RouteClassificationStep(
            qualification_expiry_rules=qualification_expiry_rules,
            duplicate_request_index=duplicate_request_index,
        )

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_case_json = state.get("normalized_case_json")
        if not normalized_case_json:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["MainNode: missing normalized_case_json from pre_process"],
            }
        normalized_case = json.loads(normalized_case_json)
        case_reference = state.get("case_reference", "")
        technician_reference = normalized_case.get("technician_reference", {}).get("normalized", "")
        site_reference = normalized_case.get("site_reference", {}).get("normalized", "")
        equipment_class = normalized_case.get("equipment_class", "unspecified")
        requirement_window = normalized_case.get("requirement_window", {})

        certification_outcome = self._certification_step.execute(
            case_reference=case_reference,
            normalized_case=normalized_case,
        )

        emit_trace_event(
            "certification_check_completed",
            {
                "case_reference": case_reference,
                "finding_count": len(certification_outcome["findings"]),
                "missing_field_count": len(certification_outcome["missing_certification_fields"])
                + len(certification_outcome["missing_site_access_fields"]),
            },
            state,
        )

        # config_unconfirmed fail-closed tracking (docs/02_design.md): OR
        # together whether EITHER step-helper is running against an
        # unconfirmed illustrative default (any of the 4 §12 In-progress
        # dependencies missing from config), so the route classification
        # always carries an explicit warning rather than silently implying
        # the result is verified.
        config_unconfirmed = self._certification_step.config_unconfirmed or self._route_step.config_unconfirmed

        route_outcome = self._route_step.classify(
            case_reference=case_reference,
            technician_reference=technician_reference,
            site_reference=site_reference,
            equipment_class=equipment_class,
            requirement_window=requirement_window,
            missing_certification_fields=certification_outcome["missing_certification_fields"],
            missing_site_access_fields=certification_outcome["missing_site_access_fields"],
            config_unconfirmed=config_unconfirmed,
        )

        emit_trace_event(
            "route_classification_completed",
            {
                "case_reference": case_reference,
                "selected_route": route_outcome["selected_route"],
                "target_queue": route_outcome["target_queue"],
                "config_unconfirmed": config_unconfirmed,
            },
            state,
        )

        return {
            "evidence_findings_json": certification_outcome["evidence_findings_json"],
            "missing_evidence_fields_json": certification_outcome["missing_evidence_fields_json"],
            "selected_route": route_outcome["selected_route"],
            "route_reasons_json": route_outcome["route_reasons_json"],
            "target_queue": route_outcome["target_queue"],
            "config_unconfirmed": config_unconfirmed,
            "status": AgentStatus.SUCCESS.value,
        }
