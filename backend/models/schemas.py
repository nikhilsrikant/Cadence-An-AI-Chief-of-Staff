"""
Cadence - Pydantic Data Models
Core domain models for commitments, decisions, people, and agent actions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import uuid4

from pydantic import BaseModel, Field


# --- Enums ---

class CommitmentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    ESCALATED = "escalated"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentActionType(str, Enum):
    NUDGE = "nudge"
    RESCHEDULE = "reschedule"
    ESCALATE = "escalate"
    TASK_SYNC = "task_sync"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class SourceType(str, Enum):
    MEETING_TRANSCRIPT = "meeting_transcript"
    SLACK_THREAD = "slack_thread"
    CALENDAR_INVITE = "calendar_invite"


# --- Core Domain Models ---

class Person(BaseModel):
    """A team member in the knowledge graph."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None


class Commitment(BaseModel):
    """A structured commitment extracted from communications."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    owner_name: str
    owner_id: Optional[str] = None
    deadline: Optional[datetime] = None
    status: CommitmentStatus = CommitmentStatus.PENDING
    priority: Priority = Priority.MEDIUM
    dependencies: List[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.MEETING_TRANSCRIPT
    source_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    meeting_title: Optional[str] = None
    blocking_count: int = 0


class Decision(BaseModel):
    """A decision that was made in a meeting or thread."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    made_by: str
    accepted_by: List[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.MEETING_TRANSCRIPT
    source_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    related_commitments: List[str] = Field(default_factory=list)


class Conflict(BaseModel):
    """A detected scheduling or resource conflict."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str  # "schedule_overlap", "overload", "dependency_chain"
    description: str
    affected_person: str
    commitment_ids: List[str]
    severity: Priority = Priority.HIGH
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False


# --- Agent Action Models ---

class AgentAction(BaseModel):
    """An action proposed by an orchestration agent."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: AgentActionType
    agent_name: str
    description: str
    target_person: str
    target_commitment_id: Optional[str] = None
    proposed_at: datetime = Field(default_factory=datetime.utcnow)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    confidence_score: float = 0.5
    message_content: Optional[str] = None
    proposed_new_deadline: Optional[datetime] = None
    escalate_to: Optional[str] = None
    executed_at: Optional[datetime] = None


# --- API Request/Response Models ---

class TranscriptInput(BaseModel):
    """Input for the commitment extraction endpoint."""
    text: str
    source_type: SourceType = SourceType.MEETING_TRANSCRIPT
    meeting_title: Optional[str] = None
    participants: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Result from commitment extraction."""
    commitments: List[Commitment]
    decisions: List[Decision]
    source_type: SourceType
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardItem(BaseModel):
    """A single item on the decision dashboard."""
    id: str
    title: str
    type: str  # "commitment", "decision", "conflict"
    urgency_score: float
    impact_score: float
    blocking_count: int
    owner: str
    deadline: Optional[datetime] = None
    status: str
    needs_action: bool = True


class ApprovalRequest(BaseModel):
    """Request to approve or reject an agent action."""
    action_id: str
    approved: bool
    reviewer_note: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    neo4j_connected: bool
    agents_running: bool
    pending_approvals: int
    total_commitments: int
