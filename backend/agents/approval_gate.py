"""
Cadence - Human Approval Gate
Every autonomous action passes through this gate before execution.
Implements configurable auto-clear threshold and full audit trail.

"Trust is the product, not a feature."
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from backend.graph.database import get_db
from backend.models.schemas import (
    AgentAction,
    AgentActionType,
    ApprovalStatus,
)
from backend.utils.logger import logger
from config.settings import settings


class ApprovalGate:
    """
    Human Approval Gate — the trust layer between agent-proposed actions
    and autonomous execution.

    Features:
    - Configurable auto-approve threshold (confidence_score >= threshold → auto-clear)
    - Manual approve/reject workflow for lower-confidence actions
    - Full audit trail of every action and its approval decision
    - Timeout mechanism for stale approvals
    - Batch approval for multiple actions

    Maps to watsonx Orchestrate's:
    - Agentic Control Plane dashboard
    - Security Control Center for governing agents in production
    """

    def __init__(self):
        self.db = get_db()
        self.auto_approve_threshold = settings.auto_approve_threshold
        self.timeout_hours = settings.approval_timeout_hours
        self._audit_log: List[Dict] = []

    # =========================================================================
    # Core Approval Operations
    # =========================================================================

    def submit_for_approval(self, action: AgentAction) -> AgentAction:
        """
        Submit an agent action through the approval gate.
        Auto-approves if confidence exceeds threshold.
        """
        # Auto-approve check
        if action.confidence_score >= self.auto_approve_threshold:
            action.approval_status = ApprovalStatus.AUTO_APPROVED
            action.executed_at = datetime.utcnow()
            self._log_audit(action, "auto_approved", "Confidence above threshold")
            logger.info(
                f"[ApprovalGate] Auto-approved: {action.description} "
                f"(confidence: {action.confidence_score:.2f} >= {self.auto_approve_threshold})"
            )
        else:
            action.approval_status = ApprovalStatus.PENDING
            self._log_audit(action, "submitted", "Awaiting human review")
            logger.info(
                f"[ApprovalGate] Queued for review: {action.description} "
                f"(confidence: {action.confidence_score:.2f} < {self.auto_approve_threshold})"
            )

        # Store in graph
        if self.db.is_connected():
            self.db.create_agent_action(action)

        return action

    def approve(self, action_id: str, reviewer_note: Optional[str] = None) -> Dict:
        """
        Manually approve an action → triggers execution.
        """
        if self.db.is_connected():
            self.db.update_action_status(
                action_id,
                ApprovalStatus.APPROVED,
                executed_at=datetime.utcnow(),
            )

        result = {
            "action_id": action_id,
            "status": "approved",
            "executed_at": datetime.utcnow().isoformat(),
            "reviewer_note": reviewer_note,
        }

        self._log_audit_entry(action_id, "approved", reviewer_note)
        logger.info(f"[ApprovalGate] Approved: {action_id}")

        # Trigger execution
        self._execute_action(action_id)

        return result

    def reject(self, action_id: str, reviewer_note: Optional[str] = None) -> Dict:
        """
        Manually reject an action → no execution.
        """
        if self.db.is_connected():
            self.db.update_action_status(action_id, ApprovalStatus.REJECTED)

        result = {
            "action_id": action_id,
            "status": "rejected",
            "reviewer_note": reviewer_note,
        }

        self._log_audit_entry(action_id, "rejected", reviewer_note)
        logger.info(f"[ApprovalGate] Rejected: {action_id}")

        return result

    def batch_approve(self, action_ids: List[str], reviewer_note: Optional[str] = None) -> List[Dict]:
        """Approve multiple actions at once."""
        results = []
        for action_id in action_ids:
            result = self.approve(action_id, reviewer_note)
            results.append(result)
        return results

    # =========================================================================
    # Query Operations
    # =========================================================================

    def get_pending_queue(self) -> List[Dict]:
        """Get all actions awaiting human approval, oldest first."""
        if not self.db.is_connected():
            return []
        return self.db.get_pending_actions()

    def get_queue_summary(self) -> Dict:
        """Get a summary of the approval queue state."""
        pending = self.get_pending_queue()

        summary = {
            "total_pending": len(pending),
            "by_agent": {},
            "by_type": {},
            "oldest_pending": None,
            "auto_approve_threshold": self.auto_approve_threshold,
        }

        for action in pending:
            agent = action.get("agent_name", "unknown")
            action_type = action.get("action_type", "unknown")

            summary["by_agent"][agent] = summary["by_agent"].get(agent, 0) + 1
            summary["by_type"][action_type] = summary["by_type"].get(action_type, 0) + 1

            proposed_at = action.get("proposed_at")
            if proposed_at and (
                summary["oldest_pending"] is None
                or str(proposed_at) < summary["oldest_pending"]
            ):
                summary["oldest_pending"] = str(proposed_at)

        return summary

    # =========================================================================
    # Timeout / Expiry
    # =========================================================================

    def expire_stale_approvals(self) -> List[str]:
        """
        Expire actions that have been pending longer than timeout_hours.
        Returns list of expired action IDs.
        """
        pending = self.get_pending_queue()
        now = datetime.utcnow()
        expired_ids = []

        for action in pending:
            proposed_at_str = action.get("proposed_at")
            if not proposed_at_str:
                continue

            try:
                proposed_at = datetime.fromisoformat(str(proposed_at_str).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            age_hours = (now - proposed_at).total_seconds() / 3600

            if age_hours > self.timeout_hours:
                action_id = action.get("id")
                if action_id:
                    self.reject(action_id, f"Auto-expired after {self.timeout_hours}h")
                    expired_ids.append(action_id)
                    logger.info(f"[ApprovalGate] Expired: {action_id} (age: {age_hours:.1f}h)")

        return expired_ids

    # =========================================================================
    # Execution
    # =========================================================================

    def _execute_action(self, action_id: str) -> None:
        """
        Execute an approved action. In production, this would:
        - Send Slack nudges
        - Update calendar events
        - Sync to task trackers
        - Notify escalation targets

        For the hackathon, we log the execution.
        """
        logger.info(f"[ApprovalGate] Executing action: {action_id}")

        # In production, dispatch based on action type:
        # - NUDGE → Send Slack message via Orchestrate connector
        # - RESCHEDULE → Update calendar via Microsoft 365 connector
        # - ESCALATE → Notify manager via Slack/email
        # - TASK_SYNC → Create/update in project management tool

    # =========================================================================
    # Audit Trail
    # =========================================================================

    def _log_audit(self, action: AgentAction, event: str, note: str) -> None:
        """Log an audit event for an action."""
        entry = {
            "id": str(uuid4()),
            "action_id": action.id,
            "agent_name": action.agent_name,
            "action_type": action.action_type.value,
            "event": event,
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence_score": action.confidence_score,
            "target_person": action.target_person,
        }
        self._audit_log.append(entry)

    def _log_audit_entry(self, action_id: str, event: str, note: Optional[str]) -> None:
        """Log a simple audit entry by action ID."""
        entry = {
            "id": str(uuid4()),
            "action_id": action_id,
            "event": event,
            "note": note or "",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._audit_log.append(entry)

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Get the most recent audit log entries."""
        return self._audit_log[-limit:]

    def get_audit_for_action(self, action_id: str) -> List[Dict]:
        """Get all audit entries for a specific action."""
        return [e for e in self._audit_log if e.get("action_id") == action_id]


# =============================================================================
# Singleton
# =============================================================================

_gate_instance: Optional[ApprovalGate] = None


def get_approval_gate() -> ApprovalGate:
    """Get the global ApprovalGate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = ApprovalGate()
    return _gate_instance
