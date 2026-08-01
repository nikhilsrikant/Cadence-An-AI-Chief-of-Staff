"""
Cadence - Follow-Up Agent
Generates friendly nudge messages for stale or approaching-deadline commitments.
Runs GENERATIVE orchestration — LLM-phrased messages for natural communication.
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import uuid4

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import AgentAction, AgentActionType
from backend.utils.logger import logger


# Nudge message templates (generative phrasing)
NUDGE_TEMPLATES = {
    "stale": [
        "Hey {person}, just checking in on '{title}' — it's been a bit since the last update. Any blockers I can help surface?",
        "Hi {person}, quick pulse check on '{title}': still on track, or should we flag anything?",
        "Friendly nudge: '{title}' hasn't moved in a few days. Let me know if priorities shifted or if there's a dependency holding things up.",
    ],
    "approaching_deadline": [
        "Hi {person}, '{title}' is due {deadline_str} — just making sure it's on your radar for this week.",
        "Hey {person}, heads up that '{title}' has a deadline coming up on {deadline_str}. All good?",
        "Quick reminder: '{title}' (owned by you) is due {deadline_str}. Let me know if the timeline still works.",
    ],
    "overdue": [
        "Hi {person}, '{title}' was due on {deadline_str} and is now overdue. Can you give a quick status update?",
        "{person}, '{title}' has passed its deadline ({deadline_str}). Should we reschedule or is it nearly done?",
        "Checking in: '{title}' is past due ({deadline_str}). Let me know the current status so I can update the team.",
    ],
}


class FollowUpAgent(BaseAgent):
    """
    Follow-Up Agent — identifies stale or overdue commitments and
    generates natural-language nudge messages.

    Decision style: GENERATIVE
    - Message phrasing varies for natural feel
    - Tone is friendly, not aggressive
    - Context-aware messaging
    """

    @property
    def name(self) -> str:
        return "followup"

    @property
    def description(self) -> str:
        return (
            "Identifies stale or approaching-deadline commitments and "
            "generates friendly nudge messages to owners."
        )

    def analyze(self) -> List[dict]:
        """
        Identify commitments that need follow-up:
        1. Stale (no update in 48+ hours)
        2. Approaching deadline (within 2 days)
        3. Overdue
        """
        if not self.db.is_connected():
            return []

        items_needing_followup = []

        # 1. Stale commitments
        from config.settings import settings
        stale = self.db.detect_stale_commitments(stale_hours=settings.escalation_stale_hours)
        for item in stale:
            items_needing_followup.append({
                "type": "stale",
                "id": item["id"],
                "title": item["title"],
                "owner": item["owner"],
                "deadline": item.get("deadline"),
                "last_updated": item.get("last_updated"),
            })

        # 2. Approaching deadline and overdue (check all active commitments)
        all_commitments = self.db.get_all_commitments()
        now = datetime.utcnow()

        for c in all_commitments:
            if c.get("status") in ("completed", "escalated"):
                continue

            deadline_str = c.get("deadline")
            if not deadline_str:
                continue

            try:
                deadline = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            days_until = (deadline - now).days

            if days_until < 0 and c.get("status") != "overdue":
                # Overdue
                items_needing_followup.append({
                    "type": "overdue",
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "owner": c.get("owner_name"),
                    "deadline": deadline_str,
                    "days_overdue": abs(days_until),
                })
            elif 0 <= days_until <= 2:
                # Approaching deadline
                items_needing_followup.append({
                    "type": "approaching_deadline",
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "owner": c.get("owner_name"),
                    "deadline": deadline_str,
                    "days_until": days_until,
                })

        return items_needing_followup

    def propose_actions(self, analysis: List[dict]) -> List[AgentAction]:
        """Generate nudge actions with natural-language messages."""
        actions = []
        import random

        for item in analysis:
            nudge_type = item["type"]
            templates = NUDGE_TEMPLATES.get(nudge_type, NUDGE_TEMPLATES["stale"])
            template = random.choice(templates)

            # Format deadline string
            deadline_str = "soon"
            if item.get("deadline"):
                try:
                    dt = datetime.fromisoformat(str(item["deadline"]).replace("Z", "+00:00"))
                    deadline_str = dt.strftime("%b %d")
                except (ValueError, TypeError):
                    deadline_str = str(item["deadline"])

            message = template.format(
                person=item.get("owner", "there"),
                title=item.get("title", "your commitment"),
                deadline_str=deadline_str,
            )

            # Confidence scoring
            confidence = {
                "stale": 0.65,
                "approaching_deadline": 0.72,
                "overdue": 0.80,
            }.get(nudge_type, 0.6)

            action = AgentAction(
                id=str(uuid4()),
                action_type=AgentActionType.NUDGE,
                agent_name=self.name,
                description=f"Follow-up nudge for '{item.get('title')}' ({nudge_type})",
                target_person=item.get("owner", "Unknown"),
                target_commitment_id=item.get("id"),
                confidence_score=confidence,
                message_content=message,
            )
            actions.append(action)

        return actions
