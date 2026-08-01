"""
Cadence - Agent Orchestrator
Coordinates the execution of all agents and aggregates results.
Maps to watsonx Orchestrate's flow builder pattern.
"""

from __future__ import annotations

from typing import Dict, List

from backend.agents.scheduler_agent import SchedulerAgent
from backend.agents.followup_agent import FollowUpAgent
from backend.agents.escalation_agent import EscalationAgent
from backend.models.schemas import AgentAction
from backend.utils.logger import logger


def run_all_agents() -> Dict[str, List[dict]]:
    """
    Execute all orchestration agents in sequence:
    1. Scheduler (deterministic) — detect and resolve conflicts
    2. Follow-up (generative) — nudge stale items
    3. Escalation (deterministic) — escalate critical items

    This mirrors watsonx Orchestrate's flow builder pattern where
    agents are chained with different decision styles.
    """
    logger.info("=" * 60)
    logger.info("CADENCE AGENT ORCHESTRATION RUN")
    logger.info("=" * 60)

    results: Dict[str, List[dict]] = {}

    # 1. Scheduler Agent (deterministic)
    try:
        scheduler = SchedulerAgent()
        scheduler_actions = scheduler.run()
        results["scheduler"] = [a.model_dump() for a in scheduler_actions]
        logger.info(f"Scheduler: {len(scheduler_actions)} actions")
    except Exception as e:
        logger.error(f"Scheduler agent failed: {e}")
        results["scheduler"] = []

    # 2. Follow-Up Agent (generative)
    try:
        followup = FollowUpAgent()
        followup_actions = followup.run()
        results["followup"] = [a.model_dump() for a in followup_actions]
        logger.info(f"Follow-up: {len(followup_actions)} actions")
    except Exception as e:
        logger.error(f"Follow-up agent failed: {e}")
        results["followup"] = []

    # 3. Escalation Agent (deterministic)
    try:
        escalation = EscalationAgent()
        escalation_actions = escalation.run()
        results["escalation"] = [a.model_dump() for a in escalation_actions]
        logger.info(f"Escalation: {len(escalation_actions)} actions")
    except Exception as e:
        logger.error(f"Escalation agent failed: {e}")
        results["escalation"] = []

    total = sum(len(v) for v in results.values())
    logger.info(f"Orchestration complete: {total} total actions proposed")
    logger.info("=" * 60)

    return results
