"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.
#
# Dict/list-shaped domain payloads are stored as Optional[str] JSON strings
# (json.dumps on write, json.loads on read) per ADR-005 — never as raw
# dict/list-of-dict objects with nested non-primitive structure beyond what
# TypedDict/msgpack safely round-trips. Simple flat lists of strings are
# stored directly (msgpack-safe).

from typing import Optional

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent.

    Field lifecycle across the 3-node / 4-step-helper pipeline
    (see docs/02_design.md "Architecture Overview" for the full mapping):

      pre_process (SecureIntakeStep)
        -> normalized_case_json, input_validation_errors, case_reference

      main (CertificationCheckStep -> RouteClassificationStep)
        -> evidence_findings_json, missing_evidence_fields_json,
           selected_route, route_reasons_json, target_queue,
           config_unconfirmed

      post_process (HumanHandoffStep)
        -> review_packet_json, advisory_label_ok
    """

    # --- pre_process / Secure Intake outputs ---
    normalized_case_json: Optional[str]  # JSON: normalized case manifest
    input_validation_errors: list[str]
    case_reference: str

    # --- main / Certification Check outputs ---
    evidence_findings_json: Optional[str]  # JSON: cited completeness/consistency findings
    missing_evidence_fields_json: Optional[str]  # JSON: list of missing/unreadable fields

    # --- main / Route Classification outputs ---
    selected_route: str
    route_reasons_json: Optional[str]  # JSON: list of {field, rule_id, original, normalized}
    target_queue: str
    config_unconfirmed: bool  # True when any §12 In-progress dependency used its illustrative default

    # --- post_process / Human Handoff outputs ---
    review_packet_json: Optional[str]  # JSON: Markdown/JSON review packet
    advisory_label_ok: bool
