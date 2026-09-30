"""AgentCore Platform v1.0"""

# Step-helper: Step 1 · Secure Intake (proposal §4).
# Pure Python — NOT a BaseNode subclass. Called from src/nodes/pre_process_node.py.
# No `agenticstar`/framework security-gate imports here (step-helpers stay
# pure Python by design); the calling FunctionNode owns S-1/S-2/S-3/S-4.

from __future__ import annotations

import json
from typing import Any


class SecureIntakeStep:
    """Authenticates the caller (via the FunctionNode's S-1 gate), validates
    permitted input types, normalizes identifiers and document metadata, and
    attaches source references (proposal §4 Step 1).

    Deterministic — no LLM parameter. Produces a normalized case manifest
    plus an input-validation result.
    """

    def execute(self, input_context: dict[str, Any]) -> dict[str, Any]:
        """Validate + normalize the raw input_context.

        Args:
            input_context: caller-supplied dict — technician certification
                and access-request records, site authorization and
                qualification records, site/equipment-class requirement
                record (proposal §4 input list).

        Returns:
            dict with keys: errors (list[str]), case_reference (str),
            normalized_case (dict) — source references attached.
        """
        errors: list[str] = []

        case_reference_raw = str(input_context.get("case_reference", "")).strip()
        if not case_reference_raw:
            errors.append("case_reference: missing or empty")

        technician_reference = str(input_context.get("technician_reference", "")).strip()
        if not technician_reference:
            errors.append("technician_reference: missing or empty")

        site_reference = str(input_context.get("site_reference", "")).strip()
        equipment_class = str(input_context.get("equipment_class", "unspecified")).strip()

        evidence_documents = input_context.get("evidence_documents", [])
        if not isinstance(evidence_documents, list):
            evidence_documents = []

        requirement_window = input_context.get("requirement_window", {})
        if not isinstance(requirement_window, dict):
            requirement_window = {}

        normalized_case = {
            "case_reference": {
                "original": input_context.get("case_reference"),
                "normalized": case_reference_raw,
            },
            "technician_reference": {
                "original": input_context.get("technician_reference"),
                "normalized": technician_reference,
            },
            "site_reference": {
                "original": input_context.get("site_reference"),
                "normalized": site_reference,
            },
            "equipment_class": equipment_class,
            "evidence_documents": [self._normalize_document(doc) for doc in evidence_documents],
            "requirement_window": requirement_window,
            "source_references": input_context.get("source_references", []),
        }

        return {
            "errors": errors,
            "case_reference": case_reference_raw,
            "normalized_case": normalized_case,
            "normalized_case_json": json.dumps(normalized_case),
        }

    @staticmethod
    def _normalize_document(doc: Any) -> dict[str, Any]:
        if not isinstance(doc, dict):
            return {"doc_type": "unknown", "readable": False, "source_ref": str(doc)}
        return {
            "doc_type": str(doc.get("doc_type", "unknown")),
            "readable": bool(doc.get("readable", False)),
            "source_ref": str(doc.get("source_ref", "")),
            "expiry_date": doc.get("expiry_date"),
        }
