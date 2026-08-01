"""
Cadence - Base Agent Class
Foundation for all orchestration agents (scheduler, follow-up, escalation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from backend.graph.database import get_db
from backend.models.schemas import AgentAction, ApprovalStatus
from backend.utils.logger import logger
from config.settings import settings


class BaseAgent(ABC):
    """
    Abstract base class for Cadence orchestration agents.
    All agents operate on the Neo4j knowledge graph and produce
    AgentActions that pass through the human approval gate.
    """

    def __init__(self):
        self.db = get_db()
        self.auto_approve_threshold = settings.auto_approve_threshold

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this agent does."""
        ...

    @abstractmethod
    def analyze(self) -> List[dict]:
        """
        Analyze the current graph state and identify items needing action.
        Returns raw analysis results.
        """
        ...

    @abstractmethod
    def propose_actions(self, analysis: List[dict]) -> List[AgentAction]:
        """
        Based on analysis results, propose concrete actions.
        Each action goes through the approval gate.
        """
        ...

    def run(self) -> List[AgentAction]:
        """
        Execute the full agent cycle:
        1. Analyze the graph
        2. Propose actions
        3. Store actions (with auto-approve for high-confidence items)
        4. Return proposed actions
        """
        logger.info(f"[{self.name}] Starting agent run")

        # Step 1: Analyze
        analysis = self.analyze()
        logger.info(f"[{self.name}] Analysis found {len(analysis)} items")

        if not analysis:
            logger.info(f"[{self.name}] Nothing to do")
            return []

        # Step 2: Propose actions
        actions = self.propose_actions(analysis)
        logger.info(f"[{self.name}] Proposed {len(actions)} actions")

        # Step 3: Store and auto-approve if confidence is high
        stored_actions = []
        for action in actions:
            action.agent_name = self.name
            action.proposed_at = datetime.utcnow()

            # Auto-approve if confidence exceeds threshold
            if action.confidence_score >= self.auto_approve_threshold:
                action.approval_status = ApprovalStatus.AUTO_APPROVED
                action.executed_at = datetime.utcnow()
                logger.info(
                    f"[{self.name}] Auto-approved: {action.description} "
                    f"(confidence: {action.confidence_score:.2f})"
                )
            else:
                action.approval_status = ApprovalStatus.PENDING
                logger.info(
                    f"[{self.name}] Pending approval: {action.description} "
                    f"(confidence: {action.confidence_score:.2f})"
                )

            # Store in graph
            if self.db.is_connected():
                self.db.create_agent_action(action)

            stored_actions.append(action)

        logger.info(f"[{self.name}] Run complete: {len(stored_actions)} actions stored")
        return stored_actions
