"""P2+ mission-critical engine (workbook Tabs 01–07, 10–13, 15, 20–26).

Phase 1 ships the decision contract, versions, and a legacy pocket-route compat
adapter. Full WBA / Hard Exit / Enhanced Sheet pipeline lands in later phases.
Import only from app.services — never from routers.
"""

from app.engine.mission.compat import decision_from_continuation
from app.engine.mission.decision import MissionDecision, build_versions
from app.engine.mission.pipeline import authority_at_click, run_pipeline
from app.engine.mission.protection import evaluate_protection, weak_recompression
from app.engine.mission.versions import (
    CONFIG_VERSION,
    ENGINE_VERSION,
    PARSER_VERSION,
    TOKEN_FORMAT,
)

__all__ = [
    "CONFIG_VERSION",
    "ENGINE_VERSION",
    "PARSER_VERSION",
    "TOKEN_FORMAT",
    "MissionDecision",
    "authority_at_click",
    "build_versions",
    "decision_from_continuation",
    "evaluate_protection",
    "run_pipeline",
    "weak_recompression",
]
