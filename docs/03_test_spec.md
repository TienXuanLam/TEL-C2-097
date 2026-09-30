# Test Specification

## Test Strategy
- Coverage target: all 3 nodes, 4 step-helper services, 5 routes, S-1→S-4 boundaries
- Test types: Unit (per service/node) / Proof-of-Boundary (framework contract) / Integration (real `agent.compile()` + `agent.invoke()`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS (`src/schemas/state.py`, verified by `test_pb02_s3_state_safety` / `test_state_safety.py`) |
| TC-02 | SecurityViolationError fires on invalid input | Error raised | PASS — `PreProcessNode._extra_security_gate_input()` rejects empty/malformed `user_input` |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations (S-5 enforcement moved to CI by the framework's credential-scan gate) | PASS (local: `tests/proof_of_boundary/test_state_safety.py`) |
| TC-04 | InvocationContext via configurable only | Direct access raises error | PASS — no node constructs `InvocationContext(...)` directly; entry point (`src/api/server.py`) is the sole exception |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | PASS — 0 duplicates (only domain events: `intake_normalization_completed`, `certification_check_completed`, `route_classification_completed`, `human_handoff_packet_composed`) |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | PASS (`tests/unit/test_framework_compliance_tc06_tc07.py`) |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | PASS (`tests/unit/test_framework_compliance_tc06_tc07.py`) |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | PASS (`tests/unit/test_trust_gate.py`, `tests/integration/test_graph.py::test_anonymous_caller_blocked_by_trust_gate`) |
| TC-09 | S-2: `_extra_security_gate_input()` non-trivial when domain checks needed | Domain-specific input checks execute correctly | PASS — `PreProcessNode` rejects empty/non-JSON/non-object `user_input` |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial when domain checks needed | Domain-specific output checks execute correctly | PASS — `PostProcessNode` blocks output when `advisory_label_ok is False` |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | PASS — ≥1 per node (see TC-05 event list) |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS (implicit — TC-11) |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS (`tests/proof_of_boundary/test_state_safety.py`) |
| PB-3 | Level 2 → External service | Real external service connection | Data retrieved | N/A — no external service calls in this template (checklist/qualification-index/duplicate-index are config-injected dicts/lists, not live service calls) |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS (`tests/proof_of_boundary/test_import_isolation.py`) |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS (`tests/proof_of_boundary/test_state_safety.py`) |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified | PASS (`tests/proof_of_boundary/test_pb_invoke_order.py`) |
| PB-7 | HITL interrupt propagation *(conditional)* | Required only when `config.yaml` sets `hitl.enabled: true`; otherwise record **Auto-waived — non-HITL** | `GraphInterrupt` propagates to the LangGraph engine; `status` is not set to `error` | **Auto-waived — non-HITL** (`config/config.yaml` has no `hitl:` block; file present, `_CONFIG_PATH` fixed to `config/config.yaml`, correctly SKIPPED — 2 tests) |

> **Pre-CoE gate checklist:** PB-1 through PB-6 are mandatory. Evaluate PB-7 only for HITL-enabled templates. When neither HITL setting is true, mark PB-7 **Auto-waived — non-HITL**; its test is not required and must not block the gate.

## Domain Business Logic Tests

| Test-ID | Test | Input | Expected Result | Result |
|---------|------|-------|----------------|--------|
| BL-01 | Clean submission (all evidence present, no expiry conflict, no duplicate) | Complete evidence set | `human_field_operations_review` (catch-all — never auto-approves) | PASS (`test_graph.py::test_full_pipeline_success_clean_submission`) |
| BL-02 | Missing certification document | `certification_record` absent | `missing_certification_evidence` → `field-operations-certification-review` | PASS (`test_graph.py::test_full_pipeline_missing_certification_document`) |
| BL-03 | Missing site-access authorisation document | `site_access_authorisation` absent | `site_access_authorisation_review` → `field-operations-certification-review` | PASS (`test_graph.py::test_full_pipeline_missing_site_access_document`) |
| BL-04 | Qualification-expiry window conflict | `requirement_window.effective_date` outside configured window | `qualification_expiry_conflict_review` → `field-operations-site-authorisation-review` | PASS (`test_graph.py::test_full_pipeline_qualification_expiry_conflict`) |
| BL-05 | Duplicate access request | `(technician_reference, site_reference, equipment_class)` already in `duplicate_request_index` | `duplicate_access_request_review` → `field-operations-site-authorisation-review` | PASS (`test_graph.py::test_full_pipeline_duplicate_access_request`) |
| BL-06 | Unreadable evidence document | Document present but `readable: false` | `evidence_insufficient` finding with source reference, no inferred value | PASS (`test_evidence_mapping_service.py::test_unreadable_document_produces_evidence_insufficient_finding`) |
| BL-07 | Deterministic routing (no LLM) | N/A — signature inspection | `classify()` has no `llm` parameter | PASS (`test_pb02_deterministic_domain_logic.py`) |
| BL-08 | `config_unconfirmed` fail-closed signal | No config injected (default agent) | `config_unconfirmed=True` in State, `route_reasons`, and output packet | PASS (`test_graph.py::test_full_pipeline_unconfigured_dependencies_surface_warning`) |
| BL-09 | Advisory-only guarantee — no action language | Real agent-generated Markdown packet | `advisory_label_ok=True`, no forbidden access/scheduling/contact phrases | PASS (`test_pb01_no_action_language.py`) |
| BL-10 | S-3 blocks forbidden-language output end-to-end | Monkeypatched route-reason text injects forbidden language | Graph-level `agent.invoke()` returns `status=error`, `output=None` (not the unsafe packet) | PASS (`test_graph.py::test_full_pipeline_s3_blocks_forbidden_language_end_to_end`) |

## Test Execution Summary
- Execution date: 2026-07-28
- Environment: `/usr/local/bin/python3.12` venv, `agenticstar-agentcore==1.0.0`
- Total tests: 84 (`pytest tests/ -q`)
- Pass: 82 / Fail: 0 / Skip: 2 (PB-7, both auto-waived non-HITL)
- `ruff check src/ tests/ scripts/`: clean
- 4 local gate scripts (`check_cat_consistency.py`, `check_dep_pinning.py`, `check_stub_tests.py`, `check_trust_level.py`): all PASS
