"""
Cadence - Escalation Agent
Flags critically overdue or blocking items for management escalation.
Runs DETERMINISTIC orchestration — rule-based, predictable escalation logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import uuid4

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import AgentAction, AgentActionType, CommitmentStatus
from backend.utils.logger import logger


class EscalationAgent(BaseAgent):
    """
    Escalation Agent — identifies items that are critically stalled,
    blocking other work, or significantly overdue, and escalates them.

    Decision style: DETERMINISTIC
    - Clear rules for when to escalate
    - Predictable, auditable behavior
    - No LLM reasoning needed
    """

    @property
    def name(self) -> str:
        return "escalation"

    @property
    def description(self) -> str:
        return (
            "Identifies critically overdue or blocking commitments "
            "and escalates them to management."
        )

    def analyze(self) -> List[dict]:
        """
        Identify items requiring escalation:
        1. Blocking chains (items blocking 2+ downstream tasks)
        2. Critically overdue (past deadline by 3+ days with no update)
        3. Ignored nudges (item was nudged but still no progress)
        """
        if not self.db.is_connected():
            return []

        escalation_candidates = []

        # 1. Blocking chains — items holding up multiple others
        blocking_chains = self.db.detect_blocking_chains()
        for item in blocking_chains:
            if item.get("blocking_count", 0) >= 2:
                escalation_candidates.append({
                    "type": "blocking_chain",
                    "id": item["id"],
                    "title": item["title"],
                    "owner": item["owner"],
                    "blocking_count": item["blocking_count"],
                    "deadline": item.get("deadline"),
                    "severity": "critical" if item["blocking_count"] >= 3 else "high",
                })

        # 2. Critically overdue items
        all_commitments = self.db.get_all_commitments()
        now = datetime.utcnow()

        for c in all_commitments:
            if c.get("status") in ("completed",):
                continue

            deadline_str = c.get("deadline")
            if not deadline_str:
                continue

            try:
                deadline = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            days_overdue = (now - deadline).days

            if days_overdue >= 3:
                escalation_candidates.append({
                    "type": "critically_overdue",
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "owner": c.get("owner_name"),
                    "deadline": deadline_str,
                    "days_overdue": days_overdue,
                    "severity": "critical" if days_overdue >= 7 else "high",
                })

        return escalation_candidates

    def propose_actions(self, analysis: List[dict]) -> List[AgentAction]:
        """
        Propose escalation actions with deterministic messaging.
        """
        actions = []

        for item in analysis:
            if item["type"] == "blocking_chain":
                action = self._escalate_blocker(item)
            elif item["type"] == "critically_overdue":
                action = self._escalate_overdue(item)
            else:
                continue

            if action:
                actions.append(action)

                # Also update commitment status to escalated
                if self.db.is_connected() and item.get("id"):
                    try:
                        self.db.update_commitment_status(
                            item["id"], CommitmentStatus.ESCALATED
                        )
                    except Exception as e:
                        logger.warning(f"Could not update status: {e}")

        return actions

    def _escalate_blocker(self, item: dict) -> AgentAction:
        """Create escalation for blocking items."""
        return AgentAction(
            id=str(uuid4()),
            action_type=AgentActionType.ESCALATE,
            agent_name=self.name,
            description=(
                f"ESCALATION: '{item['title']}' (owned by {item['owner']}) "
                f"is blocking {item['blocking_count']} downstream items"
            ),
            target_person=item["owner"],
            target_commitment_id=item.get("id"),
            confidence_score=0.90,  # High confidence — clear blocking signal
            escalate_to="manager",
            message_content=(
                f"🚨 Escalation: '{item['title']}' assigned to {item['owner']} "
                f"is currently blocking {item['blocking_count']} other commitments. "
                f"This needs immediate attention or reassignment to unblock the team."
            ),
        )

    def _escalate_overdue(self, item: dict) -> AgentAction:
        """Create escalation for critically overdue items."""
        days = item.get("days_overdue", 0)

        return AgentAction(
            id=str(uuid4()),
            action_type=AgentActionType.ESCALATE,
            agent_name=self.name,
            description=(
                f"ESCALATION: '{item['title']}' (owned by {item['owner']}) "
                f"is {days} days overdue"
            ),
            target_person=item["owner"],
            target_commitment_id=item.get("id"),
            confidence_score=0.85,  # High confidence for clearly overdue items
            escalate_to="manager",
            message_content=(
                f"🚨 Escalation: '{item['title']}' assigned to {item['owner']} "
                f"is now {days} days past its deadline. No progress has been recorded. "
                f"This requires management review — the item should be reassigned, "
                f"rescoped, or officially deprioritized."
            ),
        )
