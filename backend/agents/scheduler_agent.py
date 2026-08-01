"""
Cadence - Scheduler Agent
Detects scheduling conflicts and proposes reschedules.
Runs DETERMINISTIC orchestration — predictable, rule-based logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import AgentAction, AgentActionType, Priority
from backend.utils.logger import logger


class SchedulerAgent(BaseAgent):
    """
    Scheduler Agent — detects scheduling conflicts and overloads,
    then proposes reschedules or workload redistribution.

    Decision style: DETERMINISTIC
    - Rule-based conflict detection
    - Predictable reschedule proposals
    - No LLM reasoning needed
    """

    @property
    def name(self) -> str:
        return "scheduler"

    @property
    def description(self) -> str:
        return (
            "Detects scheduling conflicts (same person, same deadline day) "
            "and proposes reschedules to resolve them."
        )

    def analyze(self) -> List[dict]:
        """
        Detect schedule conflicts and overloaded team members.
        """
        if not self.db.is_connected():
            return []

        conflicts = []

        # 1. Same-day conflicts for same person
        schedule_conflicts = self.db.detect_schedule_conflicts()
        for conflict in schedule_conflicts:
            conflicts.append({
                "type": "schedule_overlap",
                "person": conflict["person"],
                "due_date": str(conflict["due_date"]),
                "items": conflict["conflicts"],
                "severity": "high",
            })

        # 2. Overloaded people
        overloaded = self.db.detect_overloaded_people(threshold=3)
        for overload in overloaded:
            conflicts.append({
                "type": "overload",
                "person": overload["person"],
                "load": overload["load"],
                "items": overload["commitments"],
                "severity": "medium",
            })

        return conflicts

    def propose_actions(self, analysis: List[dict]) -> List[AgentAction]:
        """
        For each conflict, propose a concrete reschedule action.
        """
        actions = []

        for item in analysis:
            if item["type"] == "schedule_overlap":
                action = self._propose_reschedule(item)
                if action:
                    actions.append(action)

            elif item["type"] == "overload":
                action = self._propose_load_balance(item)
                if action:
                    actions.append(action)

        return actions

    def _propose_reschedule(self, conflict: dict) -> AgentAction | None:
        """Propose moving one conflicting item to the next available day."""
        items = conflict["items"]
        if len(items) < 2:
            return None

        # Pick the lower-priority item to reschedule
        items_sorted = sorted(
            items,
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                x.get("priority", "medium"), 2
            ),
        )

        # Move the lowest priority item to the next day
        item_to_move = items_sorted[-1]
        original_deadline = item_to_move.get("deadline")

        # Calculate new deadline (push by 1 day)
        try:
            if original_deadline:
                original_dt = datetime.fromisoformat(str(original_deadline).replace("Z", "+00:00"))
            else:
                original_dt = datetime.utcnow()
            new_deadline = original_dt + timedelta(days=1)
        except (ValueError, TypeError):
            new_deadline = datetime.utcnow() + timedelta(days=1)

        return AgentAction(
            id=str(uuid4()),
            action_type=AgentActionType.RESCHEDULE,
            agent_name=self.name,
            description=(
                f"Reschedule '{item_to_move.get('title', 'Unknown')}' for {conflict['person']} "
                f"from {conflict['due_date']} to {new_deadline.strftime('%Y-%m-%d')} "
                f"to resolve same-day conflict"
            ),
            target_person=conflict["person"],
            target_commitment_id=item_to_move.get("id"),
            confidence_score=0.75,  # High confidence for clear schedule conflicts
            proposed_new_deadline=new_deadline,
            message_content=(
                f"Hi {conflict['person']}, you have {len(items)} commitments due on "
                f"{conflict['due_date']}. I'm proposing to move "
                f"'{item_to_move.get('title', 'one item')}' to {new_deadline.strftime('%b %d')} "
                f"to reduce the crunch. Does that work?"
            ),
        )

    def _propose_load_balance(self, overload: dict) -> AgentAction | None:
        """Propose workload alert for overloaded team members."""
        return AgentAction(
            id=str(uuid4()),
            action_type=AgentActionType.NUDGE,
            agent_name=self.name,
            description=(
                f"Workload alert: {overload['person']} has {overload['load']} "
                f"active commitments — consider redistributing"
            ),
            target_person=overload["person"],
            confidence_score=0.6,  # Medium confidence — needs human judgment
            message_content=(
                f"Heads up: {overload['person']} currently owns {overload['load']} "
                f"active commitments. You may want to review whether any can be "
                f"delegated or deprioritized."
            ),
        )
