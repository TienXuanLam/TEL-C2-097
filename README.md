# TEL-C2-097 — Telecom Field Technician Certification Access Evidence Router

> **Category**: Cat 2 (multi-step domain workflow — job-to-be-done)
> **Industry**: TEL (telecom)

## Overview

An authorised telecom field-operations user submits a field-technician access
case with approved certification, site-access authorisation, qualification,
and site/equipment-class requirement records. The agent normalizes evidence,
evaluates configured completeness and consistency checks, and routes the case
to one of five defined destinations (missing certification evidence, site
access authorisation review, qualification-expiry conflict review, duplicate
access-request review, or human field-operations review) with field-level
citations. It returns a neutral, advisory-only review packet for the
responsible human team — it does not identify technicians for outreach,
determine work scheduling, grant access, or contact technicians.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

This agent is written against the `agenticstar-agentcore` framework and is
runnable standalone via `src/api/server.py` — it does not require the wider
AgentCore platform (registry, gateway, orchestrator) to function. Outside the
platform: request authentication falls back to an optional bearer token read
from an environment variable (unset means every caller is treated as
unauthenticated), and there is no persistent checkpointer unless you wire one
yourself, so in-flight state does not survive a process restart.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
deploy/       deployment configuration and invoke payload sample
```

See `docs/` for the design spec and test specification.

## Customising

1. Adjust `config/` for your own certification / site-access checklist and route taxonomy.
2. Replace the certification, site-access, qualification, and equipment-class data sources under `src/services/` with your own read-only interfaces.
3. Review the routing rules in `src/services/consistency_validation_service.py` and the evidence checks in `src/services/evidence_mapping_service.py` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
