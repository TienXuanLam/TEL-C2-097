"""AgentCore Platform v1.0"""

# Step-helper: Step 2 · Certification Check (proposal §4).
# Pure Python — NOT a BaseNode subclass. Called from src/nodes/main_node.py.
#
# ASSUMPTION (pending confirmation from Telecom implementation team / Template
# configuration owner — see scaffold issue #2585 §12): the approved
# certification, site-access authorisation, qualification, and
# site/equipment-class requirement interfaces named in the proposal's input
# list are represented here as plain dict/list config objects injected at
# construction time (checklist, qualification_index). The exact real
# interface/schema for these sources is In progress per proposal §12 — this
# is a deterministic placeholder shape grounded only in the proposal's
# stated data-source names, to be replaced once the real interfaces are
# confirmed. See docs/02_design.md for the full callout.

from __future__ import annotations

import json
from typing import Any


class CertificationCheckStep:
    """Compares submitted evidence against the checklist, qualification
    index, and case reference (proposal §4 Step 2).

    Deterministic — no LLM parameter. Findings are cited to source
    documents; an unreadable/missing document produces an
    evidence-insufficient finding with its source reference rather than an
    inferred value (proposal Risk #1).
    """

    def __init__(
        self,
        checklist: list[dict[str, Any]] | None = None,
        qualification_index: dict[str, Any] | None = None,
    ) -> None:
        # config_unconfirmed fail-closed tracking (docs/02_design.md): track
        # whether the CALLER supplied a real config value here — used to
        # surface config_unconfirmed=True in the output so a case can never
        # be silently routed as if these unconfirmed illustrative defaults
        # were a confirmed production contract. This is a
        # traceability/fail-safe signal, not a block — the agent still
        # produces an advisory route, but every consumer of that route can
        # see it was computed against unconfirmed rules.
        self.config_unconfirmed = checklist is None or qualification_index is None
        # ASSUMPTION: checklist is a list of {"field": str, "doc_type": str,
        # "category": "certification"|"site_access", "required": bool}.
        self._checklist = checklist or self._default_checklist()
        # ASSUMPTION: qualification_index maps case_reference -> bool
        # (whether a valid qualification/certification record is on file).
        self._qualification_index = qualification_index or {}

    def execute(
        self,
        case_reference: str,
        normalized_case: dict[str, Any],
    ) -> dict[str, Any]:
        evidence_documents = normalized_case.get("evidence_documents", [])
        submitted_doc_types = {doc["doc_type"] for doc in evidence_documents if doc.get("readable")}
        unreadable_doc_types = {doc["doc_type"] for doc in evidence_documents if not doc.get("readable")}

        missing_certification_fields: list[dict[str, Any]] = []
        missing_site_access_fields: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []

        for item in self._checklist:
            field = item["field"]
            doc_type = item["doc_type"]
            category = item.get("category", "site_access")
            required = item.get("required", True)

            if doc_type in unreadable_doc_types:
                finding = {
                    "field": field,
                    "rule_id": item.get("rule_id", f"checklist:{field}"),
                    "status": "evidence_insufficient",
                    "reason": f"Document '{doc_type}' present but unreadable",
                    "source_ref": doc_type,
                }
                findings.append(finding)
                (missing_certification_fields if category == "certification" else missing_site_access_fields).append(
                    finding
                )
                continue

            if doc_type not in submitted_doc_types and required:
                finding = {
                    "field": field,
                    "rule_id": item.get("rule_id", f"checklist:{field}"),
                    "status": "missing",
                    "reason": f"Required document '{doc_type}' not submitted",
                    "source_ref": doc_type,
                }
                findings.append(finding)
                (missing_certification_fields if category == "certification" else missing_site_access_fields).append(
                    finding
                )
                continue

            findings.append(
                {
                    "field": field,
                    "rule_id": item.get("rule_id", f"checklist:{field}"),
                    "status": "present",
                    "reason": f"Document '{doc_type}' submitted and readable",
                    "source_ref": doc_type,
                }
            )

        # Qualification index cross-check (independent of checklist docs).
        if case_reference and not self._qualification_index.get(case_reference, True):
            finding = {
                "field": "qualification_record",
                "rule_id": "qualification_index:on_file",
                "status": "missing",
                "reason": f"No qualification/certification record on file for '{case_reference}'",
                "source_ref": "qualification_index",
            }
            findings.append(finding)
            missing_certification_fields.append(finding)

        result = {
            "findings": findings,
            "missing_certification_fields": missing_certification_fields,
            "missing_site_access_fields": missing_site_access_fields,
        }
        return {
            **result,
            "evidence_findings_json": json.dumps(findings),
            "missing_evidence_fields_json": json.dumps(missing_certification_fields + missing_site_access_fields),
        }

    @staticmethod
    def _default_checklist() -> list[dict[str, Any]]:
        # ASSUMPTION: a minimal deterministic default checklist grounded in
        # the proposal's stated evidence categories, used only when no real
        # checklist config is injected (§12 In-progress dependency
        # placeholder).
        return [
            {
                "field": "technician_certification_record",
                "doc_type": "certification_record",
                "category": "certification",
                "rule_id": "checklist:certification_record",
                "required": True,
            },
            {
                "field": "site_access_authorisation_record",
                "doc_type": "site_access_authorisation",
                "category": "site_access",
                "rule_id": "checklist:site_access_authorisation",
                "required": True,
            },
        ]
