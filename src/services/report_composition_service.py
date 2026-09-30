"""AgentCore Platform v1.0"""

# Step-helper: Step 4 · Human Handoff (proposal §4).
# Pure Python — NOT a BaseNode subclass. Called from src/nodes/post_process_node.py.
#
# ASSUMPTION (pending confirmation from Telecom operations owner — see
# scaffold issue #2585 §12): the exact human-queue/handoff contract is
# In progress. This module implements a Markdown+JSON review packet
# containing route, cited field-level reasons (field/rule_id/original/
# normalized), source references, and target queue name — grounded in the
# proposal's own §4 Step 4 description ("Markdown/JSON review packet and
# target human queue") and the 2 queue identifiers assumed in
# consistency_validation_service.py.

from __future__ import annotations

import json
import re
from typing import Any

ADVISORY_DISCLAIMER = (
    "ADVISORY ONLY — this output is a completeness/consistency routing "
    "recommendation. It does NOT constitute an access grant, work "
    "scheduling decision, site-access decision, or technician "
    "communication. A human reviewer in the target queue must make the "
    "final decision."
)

# Proposal Risk #4: a user must not be able to interpret the route as a
# field operations or site-access-action decision. Scan the composed packet
# for forbidden access-grant/scheduling/contact language before returning it.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\baccess\s+(is\s+)?granted\b", re.IGNORECASE),
    re.compile(r"\bapproved\s+for\s+(site\s+)?access\b", re.IGNORECASE),
    re.compile(r"\bscheduled\s+for\s+(work|dispatch)\b", re.IGNORECASE),
    re.compile(r"\bdispatch(ed)?\s+(the\s+)?technician\b", re.IGNORECASE),
    re.compile(r"\bcontact(ed)?\s+the\s+technician\b", re.IGNORECASE),
    re.compile(r"\bsite\s+access\s+(is\s+)?(confirmed|active)\b", re.IGNORECASE),
]

# S-2/S-3 sensitive-data minimization: fields never echoed verbatim into the
# human-facing packet body, only referenced by presence/status.
_SENSITIVE_FIELD_KEYS = {
    "national_id",
    "ssn",
    "date_of_birth",
    "home_address",
    "phone_number",
    "badge_number",
    "credential_number",
}

# A key-only denylist does not protect regulated-data VALUES carried in
# allow-listed fields (case_reference, source_ref, reason, original,
# normalized) — a value like a national ID or phone number could
# legitimately land in any of these free-text/identifier fields and would
# otherwise pass through untouched. These patterns are applied to every
# string VALUE in the packet (not just specific keys), matching common
# PII/regulated-identifier shapes. Implemented from the start (not as a
# post-hoc fix) per a lesson learned from a related prior template.
_SENSITIVE_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "national_id_or_ssn_formatted": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "national_id_or_ssn_unformatted": re.compile(r"\b\d{9}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"\b\+?\d{1,3}?[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"),
    "date_of_birth_iso": re.compile(r"\b(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b"),
}


def redact_sensitive_values(text: str) -> str:
    """Replace any regulated-data-shaped substring in `text` with a fixed
    redaction marker. Applied to every free-text/identifier VALUE that
    reaches the packet, not just to a fixed set of dict keys."""
    if not isinstance(text, str) or not text:
        return text
    redacted = text
    for pattern in _SENSITIVE_VALUE_PATTERNS.values():
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class HumanHandoffStep:
    """Builds the advisory review packet + target queue for human handoff.

    Validates that the result is traceable, neutral, and free of access
    grant/scheduling/site-authorisation-decision/contact conclusions
    (proposal §4 Step 4 + Risk #4).
    """

    def execute(
        self,
        case_reference: str,
        selected_route: str,
        route_reasons: list[dict[str, Any]],
        target_queue: str,
        evidence_findings: list[dict[str, Any]],
        source_references: list[str] | None = None,
        config_unconfirmed: bool = False,
    ) -> dict[str, Any]:
        minimized_reasons = [self._minimize(r) for r in route_reasons]
        minimized_findings = [self._minimize(f) for f in evidence_findings]

        packet = {
            "advisory_only": True,
            "disclaimer": ADVISORY_DISCLAIMER,
            # Surfaced on every packet from the start so no consumer
            # mistakes an unconfirmed-dependency result for a verified one
            # (docs/02_design.md "config_unconfirmed fail-closed tracking").
            "config_unconfirmed": config_unconfirmed,
            "case_reference": redact_sensitive_values(case_reference),
            "route": selected_route,
            "target_queue": target_queue,
            "reasons": minimized_reasons,
            "evidence_findings": minimized_findings,
            "source_references": [redact_sensitive_values(ref) for ref in (source_references or [])],
        }

        markdown = self._to_markdown(packet)
        advisory_label_ok = self._validate_advisory_only(markdown)

        return {
            "review_packet": packet,
            "review_packet_json": json.dumps(packet),
            "review_packet_markdown": markdown,
            "advisory_label_ok": advisory_label_ok,
        }

    @staticmethod
    def _minimize(item: dict[str, Any]) -> dict[str, Any]:
        """Drop sensitive keys AND redact regulated-data-shaped values in
        every remaining string field — a key-only denylist does not protect
        a value that happens to land in an allow-listed field like `reason`,
        `original`, `normalized`, or `source_ref`."""
        return {
            k: (redact_sensitive_values(v) if isinstance(v, str) else v)
            for k, v in item.items()
            if k.lower() not in _SENSITIVE_FIELD_KEYS
        }

    @staticmethod
    def _to_markdown(packet: dict[str, Any]) -> str:
        lines = [
            "# Field Technician Certification Access Evidence — Advisory Review Packet",
            "",
            f"> {packet['disclaimer']}",
            "",
            f"**Case Reference:** {packet['case_reference']}",
            f"**Route:** {packet['route']}",
            f"**Target Queue:** {packet['target_queue']}",
            "",
            "## Field-Level Reasons",
        ]
        for r in packet["reasons"]:
            lines.append(
                f"- `{r.get('field', '')}` (rule `{r.get('rule_id', '')}`): "
                f"{r.get('reason', '')} "
                f"(original: `{r.get('original', '')}`, normalized: `{r.get('normalized', '')}`)"
            )
        lines.append("")
        lines.append("## Evidence Findings")
        for f in packet["evidence_findings"]:
            lines.append(
                f"- `{f.get('field', '')}`: {f.get('status', '')} — {f.get('reason', '')} "
                f"(source: `{f.get('source_ref', '')}`)"
            )
        return "\n".join(lines)

    @staticmethod
    def _validate_advisory_only(markdown: str) -> bool:
        """Return True only if the packet is free of forbidden
        access-grant/scheduling/site-authorisation-decision/contact
        language (proposal Risk #4)."""
        return not any(pattern.search(markdown) for pattern in _FORBIDDEN_PATTERNS)
