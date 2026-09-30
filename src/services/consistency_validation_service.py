"""AgentCore Platform v1.0"""

# Step-helper: Step 3 · Route Classification (proposal §4).
# Pure Python — NOT a BaseNode subclass. Called from src/nodes/main_node.py.
#
# ASSUMPTION (pending confirmation from Telecom implementation team / Template
# configuration owner / Telecom operations owner — see scaffold issue #2585
# §12): the proposal names five route destinations and several read-only
# data sources but does not specify (a) the exact predicate for each route,
# (b) precedence when multiple conditions could apply simultaneously, or (c)
# the duplicate-access-request detection source. The ordered decision list
# below is a deterministic, explicit assumption — see docs/02_design.md for
# the full callout and rationale.
#
#   1. missing_certification_fields non-empty
#        -> route = "missing_certification_evidence"
#   2. missing_site_access_fields non-empty (and (1) did not already fire)
#        -> route = "site_access_authorisation_review"
#   3. qualification/certification expiry conflicts with the
#      site/equipment-class requirement window
#        -> route = "qualification_expiry_conflict_review"
#   4. (technician_reference, site_reference, equipment_class) already
#      present in duplicate_request_index
#        -> route = "duplicate_access_request_review"
#   5. otherwise (everything present, consistent, non-duplicate)
#        -> route = "human_field_operations_review"
#        (catch-all — the proposal states the agent never autonomously
#        grants access, so even a fully-clean case always routes to a human)

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

ROUTE_MISSING_CERTIFICATION = "missing_certification_evidence"
ROUTE_SITE_ACCESS_AUTHORISATION_REVIEW = "site_access_authorisation_review"
ROUTE_QUALIFICATION_EXPIRY_CONFLICT = "qualification_expiry_conflict_review"
ROUTE_DUPLICATE_ACCESS_REQUEST = "duplicate_access_request_review"
ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW = "human_field_operations_review"

QUEUE_CERTIFICATION_REVIEW = "field-operations-certification-review"
QUEUE_SITE_AUTHORISATION_REVIEW = "field-operations-site-authorisation-review"

_ROUTE_TO_QUEUE = {
    ROUTE_MISSING_CERTIFICATION: QUEUE_CERTIFICATION_REVIEW,
    ROUTE_SITE_ACCESS_AUTHORISATION_REVIEW: QUEUE_CERTIFICATION_REVIEW,
    ROUTE_QUALIFICATION_EXPIRY_CONFLICT: QUEUE_SITE_AUTHORISATION_REVIEW,
    ROUTE_DUPLICATE_ACCESS_REQUEST: QUEUE_SITE_AUTHORISATION_REVIEW,
    ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW: QUEUE_SITE_AUTHORISATION_REVIEW,
}


class RouteClassificationStep:
    """Applies deterministic route criteria (proposal §4 Step 3).

    Deterministic — the `classify` function signature intentionally has no
    `llm` parameter (PB test enforces this via inspect.signature). Route
    classification is a legally/operationally consequential decision per
    the domain rule in EngineerGuide/IMPLEMENTATION_LOG.md A4: any
    severity/threshold/escalation-trigger logic must be deterministic;
    LLM use is reserved for narrative/rationale text only, never the
    routing decision itself.
    """

    def __init__(
        self,
        qualification_expiry_rules: dict[str, Any] | None = None,
        duplicate_request_index: list[dict[str, Any]] | None = None,
    ) -> None:
        # config_unconfirmed fail-closed tracking — see
        # CertificationCheckStep for the full rationale.
        # duplicate_request_index defaulting to [] is indistinguishable
        # from "confirmed: there are no duplicates" vs "unconfigured:
        # duplicate detection cannot run at all" unless this flag is
        # tracked and surfaced.
        self.config_unconfirmed = qualification_expiry_rules is None or duplicate_request_index is None
        # ASSUMPTION: qualification_expiry_rules = {"min_days_before_today":
        # int, "max_days_after_today": int} — an allowed window relative to
        # "today" bounding retroactive/future-dated requirement windows.
        self._qualification_expiry_rules = qualification_expiry_rules or {
            "min_days_before_today": -30,
            "max_days_after_today": 180,
        }
        # ASSUMPTION: duplicate_request_index is a list of
        # {"technician_reference": str, "site_reference": str,
        # "equipment_class": str} records representing already-submitted/
        # pending access requests — introduced as part of the assumption
        # because the proposal's "checklist and routing rules" input does
        # not itself specify a duplicate-detection data source.
        self._duplicate_request_index = duplicate_request_index or []

    def classify(
        self,
        case_reference: str,
        technician_reference: str,
        site_reference: str,
        equipment_class: str,
        requirement_window: dict[str, Any],
        missing_certification_fields: list[dict[str, Any]],
        missing_site_access_fields: list[dict[str, Any]],
        config_unconfirmed: bool = False,
    ) -> dict[str, Any]:
        """Deterministic route decision. No `llm` parameter — see PB test
        `tests/proof_of_boundary/test_pb02_deterministic_domain_logic.py`.

        config_unconfirmed (True when ANY of the §12 In-progress
        dependencies — checklist, qualification_index,
        qualification_expiry_rules, duplicate_request_index — was not
        supplied via config and this step-helper fell back to its
        illustrative default) forces every route to carry an explicit
        unconfirmed-rules warning reason, and specifically prevents the
        "everything looks clean" catch-all from silently implying the
        evidence/expiry/duplicate checks were run against approved rules
        when they were not. The selected route itself is unchanged — this
        is a traceability fail-safe, not an additional block — but no
        consumer of the output can mistake an unconfirmed-config result for
        a verified one.
        """
        reasons: list[dict[str, Any]] = []
        config_unconfirmed = config_unconfirmed or self.config_unconfirmed

        if config_unconfirmed:
            reasons.append(
                {
                    "field": "routing_configuration",
                    "rule_id": "config:unconfirmed_dependency",
                    "original": "n/a",
                    "normalized": "n/a",
                    "reason": (
                        "One or more of the confirmed checklist, qualification "
                        "index, qualification-expiry rules, or duplicate-request "
                        "index was not supplied via configuration — this route "
                        "was computed against an unconfirmed illustrative "
                        "default, not a confirmed production rule set. Verify "
                        "independently before relying on this classification."
                    ),
                }
            )

        if missing_certification_fields:
            reasons.extend(self._to_reasons(missing_certification_fields, "missing_certification"))
            route = ROUTE_MISSING_CERTIFICATION
        elif missing_site_access_fields:
            reasons.extend(self._to_reasons(missing_site_access_fields, "site_access_authorisation_review"))
            route = ROUTE_SITE_ACCESS_AUTHORISATION_REVIEW
        else:
            expiry_conflict = self._check_expiry_conflict(requirement_window)
            if expiry_conflict is not None:
                reasons.append(expiry_conflict)
                route = ROUTE_QUALIFICATION_EXPIRY_CONFLICT
            elif self._is_duplicate(technician_reference, site_reference, equipment_class):
                reasons.append(
                    {
                        "field": "technician_reference",
                        "rule_id": "duplicate_request_index:pending_request",
                        "original": technician_reference,
                        "normalized": technician_reference,
                        "reason": (
                            f"A pending/submitted access request for site "
                            f"'{site_reference}' / equipment class "
                            f"'{equipment_class}' already exists for technician "
                            f"'{technician_reference}'"
                        ),
                    }
                )
                route = ROUTE_DUPLICATE_ACCESS_REQUEST
            else:
                reasons.append(
                    {
                        "field": "overall_submission",
                        "rule_id": "route:human_field_operations_review_default",
                        "original": "n/a",
                        "normalized": "n/a",
                        "reason": (
                            "All evidence present and consistent; agent never "
                            "autonomously grants access — routed to human "
                            "field-operations review"
                        ),
                    }
                )
                route = ROUTE_HUMAN_FIELD_OPERATIONS_REVIEW

        target_queue = _ROUTE_TO_QUEUE[route]
        return {
            "selected_route": route,
            "route_reasons": reasons,
            "route_reasons_json": json.dumps(reasons),
            "target_queue": target_queue,
            "config_unconfirmed": config_unconfirmed,
        }

    def _check_expiry_conflict(self, requirement_window: dict[str, Any]) -> dict[str, Any] | None:
        requirement_date = requirement_window.get("effective_date") if requirement_window else None
        if not requirement_date:
            # No requirement window supplied at all — nothing to conflict
            # check against; not itself an expiry conflict.
            return None
        try:
            requirement = datetime.strptime(str(requirement_date), "%Y-%m-%d").date()
        except ValueError:
            return {
                "field": "requirement_window.effective_date",
                "rule_id": "qualification_expiry_rules:unparsable",
                "original": requirement_date,
                "normalized": str(requirement_date),
                "reason": "Site/equipment-class requirement effective date is not in normalized ISO format",
            }
        delta_days = (requirement - date.today()).days
        min_days = self._qualification_expiry_rules["min_days_before_today"]
        max_days = self._qualification_expiry_rules["max_days_after_today"]
        if delta_days < min_days or delta_days > max_days:
            return {
                "field": "requirement_window.effective_date",
                "rule_id": "qualification_expiry_rules:window",
                "original": requirement_date,
                "normalized": str(requirement_date),
                "reason": (
                    f"Requirement effective date is {delta_days} days from "
                    f"today, outside allowed qualification-expiry window "
                    f"[{min_days}, {max_days}] days"
                ),
            }
        return None

    def _is_duplicate(self, technician_reference: str, site_reference: str, equipment_class: str) -> bool:
        return any(
            entry.get("technician_reference") == technician_reference
            and entry.get("site_reference") == site_reference
            and entry.get("equipment_class") == equipment_class
            for entry in self._duplicate_request_index
        )

    @staticmethod
    def _to_reasons(fields: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
        return [
            {
                "field": f["field"],
                "rule_id": f["rule_id"],
                "original": f.get("source_ref", ""),
                "normalized": f.get("status", ""),
                "reason": f["reason"],
            }
            for f in fields
        ]
