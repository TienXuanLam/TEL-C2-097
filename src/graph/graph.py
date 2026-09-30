"""AgentCore Platform v1.0"""

# Cat 2 — TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent
#
# AgentBaseGraph only has 3 real slots: pre_process / main / post_process.
# The proposal's §4 describes 4 logical steps (Secure Intake, Certification
# Check, Route Classification, Human Handoff) — more than 3, so per
# PLAYBOOK A2 this uses the step-helper pattern:
#
#   pre_process (FunctionNode)   -> SecureIntakeStep.execute()
#   main (FunctionNode)          -> CertificationCheckStep.execute()
#                                 -> RouteClassificationStep.classify()
#   post_process (FunctionNode)  -> HumanHandoffStep.execute()
#
# See docs/02_design.md "Architecture Overview" for the full diagram.

from framework.graph.agent_base_graph import AgentBaseGraph
from src.nodes.main_node import MainNode
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State


class TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent(AgentBaseGraph):
    """Fixed-pipeline Cat 2 graph — telecom field technician certification
    access evidence routing."""

    @property
    def name(self) -> str:
        return "TelecomFieldTechnicianCertificationAccessEvidenceRouterAgent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        # ASSUMPTION (§12 In-progress dependency — see docs/02_design.md):
        # the real checklist / qualification-index / qualification-expiry-
        # rules / duplicate-request-index interfaces are not yet confirmed.
        # They are read here from self.config (with deterministic defaults
        # inside each step-helper's __init__ when absent) so a real
        # KB/config object can be substituted later without touching node
        # code.
        checklist = self.config.get("checklist") if self.config else None
        qualification_index = self.config.get("qualification_index") if self.config else None
        qualification_expiry_rules = self.config.get("qualification_expiry_rules") if self.config else None
        duplicate_request_index = self.config.get("duplicate_request_index") if self.config else None

        # A6 wiring checklist (EngineerGuide/IMPLEMENTATION_LOG.md): MainNode
        # is the only node with extra constructor dependencies — verify all
        # four are passed here, not just the "obvious" one. Only a real e2e
        # agent.invoke() test catches a missed dependency (it silently
        # defaults inside the step-helper instead of raising).
        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = MainNode(
            checklist=checklist,
            qualification_index=qualification_index,
            qualification_expiry_rules=qualification_expiry_rules,
            duplicate_request_index=duplicate_request_index,
        )
        self._nodes["post_process"] = PostProcessNode()
