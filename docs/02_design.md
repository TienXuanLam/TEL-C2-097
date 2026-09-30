# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent`
- **L1 Base**: `AgentBaseGraph` (direct inheritance)
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Implementation status note

This design proceeded to implementation despite scaffold issue #2585 §12
listing three dependencies as **In progress** (approved certification /
access-request / qualification / site-authorisation / site-equipment-class
interfaces; configurable certification and site-access checklist and route
taxonomy; field-operations review queues and Markdown/JSON handoff
contract). This is an **explicit user override** of the default "wait for
confirmation before design" posture — the proposal itself carries **no Hard
Blocker** (Conditional Go, 29/35, named owners already in progress). Every
design element that fills an In-progress-dependency gap is grounded only in
what the proposal DOES specify — the 4-step workflow, the 5 named route
destinations, and the read-only data-source list — and is flagged below as
an `ASSUMPTION` callout for the named owner (Telecom implementation team /
Template configuration owner / Telecom operations owner) to confirm or
correct.

## Architecture Overview

### Node-count reconciliation (4 logical steps → 3 framework slots)

`AgentBaseGraph` provides exactly 3 domain slots: `pre_process`, `main`,
`post_process`. The proposal's §4 Agent Workflow describes 4 logical steps.
Per PLAYBOOK A2, each logical step is a pure-Python **step-helper class**
(method `execute()`/`classify()`, does **not** inherit `BaseNode`), invoked
from inside the 3 real `FunctionNode`s:

```
                        ┌─────────────────────────────────────────┐
[Authorised caller]     │              pre_process                │
      │                 │  SecureIntakeStep.execute()              │
      ▼                 │  (Step 1 · Secure Intake)                │
  initialize             └──────────────────┬────────────────────┘
      │                                     ▼
      │                 ┌─────────────────────────────────────────┐
      │                 │                  main                    │
      │                 │  CertificationCheckStep.execute()        │
      │                 │  (Step 2 · Certification Check)          │
      │                 │            │                             │
      │                 │            ▼                             │
      │                 │  RouteClassificationStep.classify()      │
      │                 │  (Step 3 · Route Classification)         │
      │                 └──────────────────┬────────────────────┘
      │                                     ▼
      │                 ┌─────────────────────────────────────────┐
      │                 │              post_process                │
      │                 │  HumanHandoffStep.execute()              │
      │                 │  (Step 4 · Human Handoff)                │
      │                 └──────────────────┬────────────────────┘
      │                                     ▼
      ▼                                  finalize
  [Output: field-level evidence + human-review route]
      ├─► field-operations-certification-review queue
      └─► field-operations-site-authorisation-review queue
```

### Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | session_id, trace_id, caller_trust_level | InitializeNode (default) |
| pre_process | Secure Intake: authenticate, validate permitted input types, normalize identifiers/metadata | `user_input` (JSON-encoded case manifest string — the real `/invoke` contract forwards `agent.invoke(req.input, ctx=ctx)`, which becomes `state["user_input"]`; there is NO separate `input_context` channel) | `normalized_case_json`, `case_reference`, `input_validation_errors`, `status` | `FunctionNode` |
| main | Certification Check + Route Classification | `normalized_case_json`, `case_reference` | `evidence_findings_json`, `missing_evidence_fields_json`, `selected_route`, `route_reasons_json`, `target_queue`, `config_unconfirmed`, `status` | `FunctionNode` |
| post_process | Human Handoff: compose the advisory review packet | `case_reference`, `selected_route`, `target_queue`, `route_reasons_json`, `evidence_findings_json` | `review_packet_json`, `advisory_label_ok`, `formatted_output`, `status` | `FunctionNode` |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Step Detail

| Step (proposal §4) | Step-helper class | Called from | Core Logic | Output |
|---|---|---|---|---|
| 1. Secure Intake | `SecureIntakeStep` (`src/services/intake_normalization_service.py`) | `pre_process` | Validate permitted input types, normalize identifiers/document metadata, attach source references | Normalized case manifest + input-validation errors |
| 2. Certification Check | `CertificationCheckStep` (`src/services/evidence_mapping_service.py`) | `main` | Compare submitted evidence against the configured certification/site-access readiness checklist | Cited completeness/consistency findings, missing-evidence field lists |
| 3. Route Classification | `RouteClassificationStep` (`src/services/consistency_validation_service.py`) | `main` | Deterministic ordered-decision-list route selection (no `llm` param) | One of 5 routes + field-level reasons + target queue |
| 4. Human Handoff | `HumanHandoffStep` (`src/services/report_composition_service.py`) | `post_process` | Compose Markdown/JSON review packet; validate advisory-only / no-access-decision language; minimize sensitive fields | Review packet + target queue |

### Data Flow

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry, if status="retry")
                                          pre_process
```

`main` always returns `status=success` or `status=error` (no domain retry
condition defined — evidence-insufficient outcomes are still a valid
`success` routing result per proposal §4 Notes: "the output states
uncertainty rather than inferring missing facts", not a pipeline failure).

## State Definition

| Field | Type | Producer | Consumer | ADR-005 Note |
|---|---|---|---|---|
| `normalized_case_json` | `Optional[str]` (JSON) | pre_process | main, post_process | Dict-shaped payload stored as JSON string per ADR-005 — `json.dumps`/`json.loads`, never a raw dict/object |
| `input_validation_errors` | `list[str]` | pre_process | (error_log surface) | Flat list of strings — msgpack-safe directly, no JSON-string wrapping needed |
| `case_reference` | `str` | pre_process | main, post_process | Primitive |
| `evidence_findings_json` | `Optional[str]` (JSON) | main | post_process | List-of-dict payload — JSON string per ADR-005 |
| `missing_evidence_fields_json` | `Optional[str]` (JSON) | main | (diagnostic) | List-of-dict payload — JSON string per ADR-005 |
| `selected_route` | `str` | main | post_process | Primitive — one of the 5 route identifiers |
| `route_reasons_json` | `Optional[str]` (JSON) | main | post_process | List-of-dict payload (field/rule_id/original/normalized) — JSON string per ADR-005 |
| `target_queue` | `str` | main | post_process | Primitive — one of the 2 queue identifiers |
| `config_unconfirmed` | `bool` | main | post_process, final output packet | Primitive — True when any §12 In-progress dependency used its illustrative default (see ASSUMPTIONS below) |
| `review_packet_json` | `Optional[str]` (JSON) | post_process | (final output) | Dict-shaped payload — JSON string per ADR-005 |
| `advisory_label_ok` | `bool` | post_process | S-3 gate | Primitive |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## ASSUMPTIONS — §12 In-progress Dependencies

> **ASSUMPTION (pending confirmation from Telecom implementation team / Template configuration owner / Telecom operations owner — see scaffold issue #2585 §12):**
> **Route predicate order.** The proposal names 5 route destinations
> (missing_certification_evidence, site_access_authorisation_review,
> qualification_expiry_conflict_review, duplicate_access_request_review,
> human_field_operations_review) and the read-only input data sources but
> does not specify per-route predicates or precedence when multiple
> conditions could apply. This design uses an ordered decision list,
> evaluated top-down, implemented in `RouteClassificationStep.classify()`:
> 1. `missing_certification_fields` non-empty → `missing_certification_evidence`
> 2. else `missing_site_access_fields` non-empty → `site_access_authorisation_review`
> 3. else qualification/certification expiry conflicts with the site/equipment-class
>    requirement window → `qualification_expiry_conflict_review`
> 4. else `(technician_reference, site_reference, equipment_class)` already in
>    the duplicate-request index → `duplicate_access_request_review`
> 5. else → `human_field_operations_review` (a fully clean case still always
>    routes to a human — the proposal states the agent never grants access or
>    makes an autonomous decision, so there is no "auto-approve" outcome; this
>    route is also the explicit catch-all)
>
> Rationale for this precedence: evidence completeness (1-2) is checked
> before expiry/duplicate consistency (3-4) because an incomplete submission
> cannot be reliably evaluated for expiry or duplicate conflicts — the fields
> needed for those checks may themselves be among the missing/unreadable
> evidence. Missing certification (1) outranks missing site-access
> authorisation (2) because a certification gap blocks eligibility entirely,
> while a site-access authorisation gap is a narrower, single-site scoping
> issue — consistent with proposal §11 Risk #3 (sensitive technician/site
> information exposure) treating identity/eligibility gaps as the
> higher-risk category to surface first.

> **ASSUMPTION (pending confirmation from Telecom implementation team — see scaffold issue #2585 §12):**
> **Missing-evidence field split.** The checklist item's `category` field
> (`"certification"` vs `"site_access"`) determines whether a
> missing/unreadable document routes to `missing_certification_evidence` or
> `site_access_authorisation_review`. The concrete checklist content itself
> (`CertificationCheckStep._default_checklist()`) is a minimal deterministic
> placeholder — 2 illustrative items (`certification_record`,
> `site_access_authorisation`) — grounded only in the proposal's evidence
> category language, not a real approved checklist. Real checklist content
> must be injected via `graph.py`'s `register_nodes()` →
> `self.config["checklist"]` once the Template configuration owner confirms
> the taxonomy.

> **ASSUMPTION (pending confirmation from Template configuration owner — see scaffold issue #2585 §12):**
> **Qualification-expiry rule shape.** `qualification_expiry_rules` is
> assumed to be a `{"min_days_before_today": int, "max_days_after_today": int}`
> window (default `[-30, 180]` days) checked against the requirement's
> effective/expiry date in `RouteClassificationStep._check_expiry_conflict()`.
> The proposal names "site/equipment-class requirement record" and
> "qualification-expiry conflict review" but does not specify the rule shape
> or default window values — these defaults are illustrative placeholders
> only.

> **ASSUMPTION (pending confirmation from Template configuration owner — see scaffold issue #2585 §12):**
> **Duplicate-access-request detection source.** The proposal's input list
> does not name a duplicate-detection data source explicitly (only "approved
> checklist and routing rules"). This design introduces a
> `duplicate_request_index` — a list of `{"technician_reference": str,
> "site_reference": str, "equipment_class": str}` records — as part of the
> assumption, grounded in the proposal's stated route destination
> "duplicate access-request review". The real interface for this index
> (e.g. a live query against a field-operations case-tracking system) is
> Unknown and must be confirmed before production use; the current default
> is an empty list (never flags a duplicate) when not injected.

> **ASSUMPTION (pending confirmation from Telecom operations owner — see scaffold issue #2585 §12):**
> **Human queue/handoff schema.** The proposal states the packet is
> "Markdown/JSON review packet" and "target human queue" but does not name
> the exact queue identifiers. This design uses exactly 2 queue identifiers,
> mapped from the 5 routes in `consistency_validation_service.py`:
> - `field-operations-certification-review` ← `missing_certification_evidence`,
>   `site_access_authorisation_review` (identity/eligibility document
>   fix-up is a certification-desk task)
> - `field-operations-site-authorisation-review` ← `qualification_expiry_conflict_review`,
>   `duplicate_access_request_review`, `human_field_operations_review`
>   (judgment/site-authorisation calls)
>
> The review packet itself (`HumanHandoffStep`) contains: `route`,
> field-level `reasons` (field name + rule_id + original vs normalized
> value), `evidence_findings`, `source_references`, `target_queue`, and an
> `advisory_only` + `disclaimer` field. Both a `review_packet_json` (JSON
> string, ADR-005) and a `review_packet_markdown` rendering are produced;
> only the JSON form is persisted to State (the Markdown form is
> regenerable from the JSON and is not stored to avoid duplicating the same
> data in two state fields).

## `config_unconfirmed` fail-closed tracking (mandatory, all §12 gaps)

Per explicit user requirement (grounded in a lesson learned from a related
prior template, which was blocked in review for silently using placeholder
defaults with no signal): every step-helper whose constructor receives
`None` for a config-provided dependency (checklist, qualification_expiry
index, duplicate index, etc.) sets `self.config_unconfirmed = True`. `main`
(`MainNode.execute()`) ORs together `config_unconfirmed` from both
step-helpers it drives (`CertificationCheckStep`, `RouteClassificationStep`)
and returns it as a State field. `RouteClassificationStep.classify()`
additionally prepends an explicit `route_reasons` entry
(`rule_id: "config:unconfirmed_dependency"`) whenever this flag is set, and
`HumanHandoffStep` surfaces the same flag as a top-level `config_unconfirmed`
field on the final review packet. This means no consumer of the output —
whether reading `route_reasons`, the top-level packet field, or raw State —
can mistake an unconfirmed-default routing result for a verified production
decision. This is a traceability fail-safe, not an additional block: the
agent still always produces an advisory route per proposal §3.

## Security Design (S-1 → S-4)

| Layer | Implementation | Mapped Proposal Risk |
|---|---|---|
| S-1 Trust Gate | All 3 `FunctionNode`s declare `required_trust_level = TrustLevel.VERIFIED_EXTERNAL` explicitly (not inherited ANONYMOUS default) — proposal describes "an authorised telecom field-operations user", not an anonymous caller | Implicit precondition for all risks below |
| S-2 Input Gate | `PreProcessNode._extra_security_gate_input()` rejects requests with an empty/malformed/non-object `user_input` manifest before normalization runs (sets `status=ERROR`, does not raise); the manifest arrives as `state["user_input"]` (real `/invoke` contract — no `input_context` channel exists) | Risk #1 (source record incomplete or unreadable) — partial coverage; full coverage happens inside `SecureIntakeStep`/`CertificationCheckStep`, which return `evidence_insufficient` findings with source references rather than inferring content |
| S-3 Output Gate | `PostProcessNode._extra_security_gate_output()` raises `RuntimeError` (blocks output) if `advisory_label_ok` is `False` — i.e. the composed packet contains forbidden access-grant/work-scheduling/site-authorisation-decision/contact language | Risk #4 (user interprets the route as a field-operations or site-access-action decision) |
| S-3 Minimization | `HumanHandoffStep._minimize()` strips a denylist of sensitive field keys (national ID, date of birth, phone, home address, badge/credential number) AND redacts regulated-data-shaped substrings (SSN/national-ID, phone, email, DOB patterns via `redact_sensitive_values()`) from every string value in `reasons`/`evidence_findings`/`case_reference`/`source_references` — closing the gap where a sensitive value could reach an allow-listed field (e.g. `reason`, `source_ref`) untouched by the key-only denylist | Risk #3 (sensitive technician or site authorization information exposed beyond the authorised review context) |
| S-4 Audit Logging | `emit_trace_event()` called at least once per node's `execute()`: `intake_normalization_completed` (pre_process), `certification_check_completed` + `route_classification_completed` (main), `human_handoff_packet_composed` (post_process) | Traceability for Risk #2 (rule applied to incorrect normalized field) — original + normalized values + rule_id + field are always preserved and logged |

Risk #2 (a configured rule applied to an incorrect normalized field) is
additionally mitigated structurally: `SecureIntakeStep` always preserves
both `original` and `normalized` values in the normalized case manifest, and
every route reason cites its `rule_id` + `field` — enabling a human reviewer
to audit rule-to-field application directly from the review packet, per
proposal §11 Risk #2 mitigation text.

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle) — obtained via `InvocationContext.from_state(state)` where secrets are needed (none currently required — no external services called; kept as a documented extension point)
- [ ] ConnectionPolicy (retry/timeout strategy) — not used; no external service calls
- [ ] SecurityViolationError — not raised directly; S-3 hook raises plain `RuntimeError` (framework maps to `AgentStatus.ERROR`)
- [x] S-2: `_extra_security_gate_input()` — `PreProcessNode` rejects empty/malformed `user_input`
- [x] S-3: `_extra_security_gate_output()` — `PostProcessNode` blocks non-advisory-only output
- [x] S-4: `emit_trace_event()` — one or more domain events per node, all 3 nodes

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: Standalone (3 `FunctionNode`s + 4 step-helper classes; no `GraphNode`/`RemoteAgentNode` composition)
- **Composition target**: N/A
- **Error propagation strategy**: N/A (no subgraph/remote composition)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: `framework/` and `shared/` only (no `agents/base/` required)

## Class Name Consistency

| Source | Value |
|---|---|
| `config/agent.yaml` → `agent.id` | `TEL-C2-097` |
| `config/agent.yaml` → `agent.name` | `Telecom Field Technician Certification Access Evidence Router` |
| `config/agent.yaml` → `agent.class` | `TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent` |
| `src/graph/graph.py` class name | `TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent` |
| `README.md` category line | Cat 2 |
| Python identifier validity | `"TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent".isidentifier()` → `True` |

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | `AgentBaseGraph` | `AutonomousBaseGraph` | `AgentBaseGraph` | Fixed 4-step deterministic pipeline, no self-directed think→act→observe loop or agent-decided termination — Cat 2 default |
| Node-count reconciliation | Force-fit 4 steps into `pre_process`/`main`/`post_process` with logic mixed inline, undocumented | Step-helper pattern: 4 pure-Python step-helper classes called from inside 3 real `FunctionNode`s | Step-helper pattern | Keeps each step independently unit-testable and readable; matches the precedent used by several prior templates in this pattern family |
| Route classification: deterministic vs LLM | Deterministic ordered decision list (no `llm` param) | LLM-driven classification with rationale generation | Deterministic | Proposal explicitly frames routing as an advisory-only, non-autonomous decision ("the agent does not... grant access"); deterministic classification is auditable, reproducible, and testable via signature inspection (PB test). LLM use, if ever added, is scoped to narrative/rationale text only, never the routing decision itself |
| HITL scope | Real `interrupt()` D6 pattern with suspend/resume | Advisory-only-label + forbidden-language-scan pattern (no `interrupt()`) | Advisory-only-label pattern | TEL is not in the HITL-mandatory regulated-industry set (HCR/INS/FIN/GOV); proposal's "Human Handoff" step is a routing output delivered to a queue, not an in-pipeline technical sign-off checkpoint — PLAYBOOK A5 default for "recommend review" language |
| PII/regulated-data handling | No redaction; pass all input fields through to the review packet | Minimize a denylist of sensitive field keys, AND redact regulated-data-shaped values (national-ID/phone/email/DOB patterns) from every string field before packet composition | Minimize + value redaction | Proposal Risk #3 (sensitive technician/site authorization information exposure) — least-privilege, minimized output required. A key-only denylist alone does not protect a sensitive value that lands in an allow-listed field like `reason`/`source_ref`/`case_reference`; `redact_sensitive_values()` in `report_composition_service.py` closes that gap from the start (avoiding a similar gap found post-hoc in a related prior template) |
| Unconfirmed §12 dependency handling | Silently use the illustrative default and produce a route indistinguishable from a verified-config result | Track `config_unconfirmed` per step-helper, surface it in `route_reasons`, State, and the output packet | Surface `config_unconfirmed` from the start | A related prior template was blocked in review for exactly the silent-default failure mode; this template implements the fail-closed `config_unconfirmed` signal in the initial implementation rather than as a post-hoc fix — every output can be distinguished as verified vs unconfirmed, and the agent still always produces an advisory route per proposal §3 |
| Sensitive-field detection regex approach | Bare two-capitalized-word pattern for name detection | Cue-word-gated pattern (name-introducing cue word required, capitalization check scoped outside case-insensitive flag) / explicit sensitive-key denylist + value-pattern redaction (no name-detection regex at all) | Explicit denylist + value-pattern redaction | Bare capitalization patterns false-positive on the agent's own generated Markdown headings ("Case Reference", "Route Classification") — known failure mode per PLAYBOOK A8; this template avoids name-detection regex entirely by keying off field names and regulated-data value shapes (ID/phone/email/DOB patterns), verified by `tests/proof_of_boundary/test_pb03_output_field_minimization.py` proving real generated headings survive untouched |
