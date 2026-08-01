"""
Cadence - Demo Seed Data
Pre-loads the Neo4j graph with realistic data for demonstrations.
Creates a scenario with conflicts, dependencies, and items needing decisions.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.graph.database import init_db
from backend.models.schemas import (
    AgentAction,
    AgentActionType,
    Commitment,
    CommitmentStatus,
    Decision,
    Person,
    Priority,
    SourceType,
)


def seed_demo_data():
    """Populate the graph with a realistic demo scenario."""
    print("🌱 Seeding demo data...")

    db = init_db()
    db.clear_all()
    db.init_schema()

    # --- People ---
    people = [
        Person(name="Sarah Chen", email="sarah@company.com", role="VP Engineering", team="Engineering"),
        Person(name="Marcus Johnson", email="marcus@company.com", role="Frontend Lead", team="Frontend"),
        Person(name="Priya Patel", email="priya@company.com", role="Backend Lead", team="Backend"),
        Person(name="David Kim", email="david@company.com", role="Data Engineer", team="Platform"),
        Person(name="Lisa Wong", email="lisa@company.com", role="Security Lead", team="Security"),
    ]

    for person in people:
        db.upsert_person(person)
    print(f"  ✅ Created {len(people)} people")

    # --- Commitments ---
    now = datetime.utcnow()

    commitments = [
        # Marcus - Frontend Migration Plan (due in 5 days)
        Commitment(
            id=str(uuid4()),
            title="Complete React migration plan",
            description="Full technical design document for migrating the customer dashboard from Vue to React",
            owner_name="Marcus Johnson",
            deadline=now + timedelta(days=5),
            status=CommitmentStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # Priya - Performance Audit (due tomorrow - approaching deadline)
        Commitment(
            id=str(uuid4()),
            title="Complete API performance audit",
            description="Full audit of slow endpoints and database query performance issues",
            owner_name="Priya Patel",
            deadline=now + timedelta(days=1),
            status=CommitmentStatus.PENDING,
            priority=Priority.HIGH,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # David - Query Optimization (due in 2 days, depends on Priya's audit)
        Commitment(
            id=str(uuid4()),
            title="Optimize database queries for slow endpoints",
            description="Focus on unoptimized joins identified in Priya's performance audit",
            owner_name="David Kim",
            deadline=now + timedelta(days=2),
            status=CommitmentStatus.PENDING,
            priority=Priority.HIGH,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # Lisa - SOC2 Review (due in 3 days - CONFLICT: same day as auth review)
        Commitment(
            id=str(uuid4()),
            title="Complete SOC2 security compliance review",
            description="Full security review for SOC2 certification - critical and non-negotiable",
            owner_name="Lisa Wong",
            deadline=now + timedelta(days=3),
            status=CommitmentStatus.IN_PROGRESS,
            priority=Priority.CRITICAL,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # Lisa - Auth Module Review (SAME DAY as SOC2 - creates conflict)
        Commitment(
            id=str(uuid4()),
            title="Review auth module for React migration",
            description="Two-hour review session with Marcus on authentication patterns for new dashboard",
            owner_name="Lisa Wong",
            deadline=now + timedelta(days=3),
            status=CommitmentStatus.PENDING,
            priority=Priority.MEDIUM,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # David - Update Roadmap (overdue - was due 2 days ago)
        Commitment(
            id=str(uuid4()),
            title="Update roadmap to reflect Q1 mobile postponement",
            description="Update the product roadmap document to show mobile app pushed to Q1",
            owner_name="David Kim",
            deadline=now - timedelta(days=2),
            status=CommitmentStatus.PENDING,
            priority=Priority.MEDIUM,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # Sarah - Exec Presentation (due in 8 days)
        Commitment(
            id=str(uuid4()),
            title="Prepare Q4 exec presentation",
            description="Executive team presentation on Q4 product plans, scheduled for Oct 25",
            owner_name="Sarah Chen",
            deadline=now + timedelta(days=8),
            status=CommitmentStatus.PENDING,
            priority=Priority.HIGH,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # All leads - Section summaries (due in 6 days, blocks Sarah's presentation)
        Commitment(
            id=str(uuid4()),
            title="Submit Q4 section summaries to Sarah",
            description="Each lead sends their section summary for the exec presentation",
            owner_name="Marcus Johnson",
            deadline=now + timedelta(days=6),
            status=CommitmentStatus.PENDING,
            priority=Priority.MEDIUM,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
        ),
        # Stale item (last updated 3 days ago)
        Commitment(
            id=str(uuid4()),
            title="Review updated OKRs and provide sign-off",
            description="All leads need to review and sign off on Q4 OKRs",
            owner_name="Priya Patel",
            deadline=now + timedelta(days=4),
            status=CommitmentStatus.PENDING,
            priority=Priority.MEDIUM,
            source_type=SourceType.MEETING_TRANSCRIPT,
            meeting_title="Q4 Product Planning Meeting",
            updated_at=now - timedelta(days=3),
        ),
    ]

    for commitment in commitments:
        db.create_commitment(commitment)
    print(f"  ✅ Created {len(commitments)} commitments")

    # Create dependency: David's query optimization depends on Priya's audit
    # (commitments[2] depends on commitments[1])
    db._link_dependencies(commitments[2].id, [commitments[1].id])

    # Sarah's exec presentation depends on section summaries
    db._link_dependencies(commitments[6].id, [commitments[7].id])

    print("  ✅ Created dependency relationships")

    # --- Decisions ---
    decisions = [
        Decision(
            title="Adopt React for new customer dashboard",
            description="Team decided to use React instead of Vue for the new customer dashboard rebuild",
            made_by="Sarah Chen",
            source_type=SourceType.MEETING_TRANSCRIPT,
        ),
        Decision(
            title="Postpone mobile app update to Q1",
            description="Mobile app update deprioritized due to bandwidth constraints; moved to Q1",
            made_by="Sarah Chen",
            source_type=SourceType.MEETING_TRANSCRIPT,
        ),
        Decision(
            title="SOC2 review is top priority for Lisa",
            description="SOC2 compliance review takes precedence over all other security work",
            made_by="Sarah Chen",
            source_type=SourceType.MEETING_TRANSCRIPT,
        ),
    ]

    for decision in decisions:
        db.create_decision(decision)
    print(f"  ✅ Created {len(decisions)} decisions")

    # --- Sample Agent Actions (pending approval) ---
    actions = [
        AgentAction(
            action_type=AgentActionType.RESCHEDULE,
            agent_name="scheduler",
            description="Reschedule 'Review auth module for React migration' for Lisa Wong to resolve same-day conflict with SOC2 review",
            target_person="Lisa Wong",
            target_commitment_id=commitments[4].id,
            confidence_score=0.65,
            proposed_new_deadline=now + timedelta(days=4),
            message_content="Hi Lisa, you have the SOC2 review and the auth module review both due the same day. I'm proposing to move the auth review to the following day. Does that work?",
        ),
        AgentAction(
            action_type=AgentActionType.NUDGE,
            agent_name="followup",
            description="Follow-up nudge for 'Update roadmap' (overdue by 2 days)",
            target_person="David Kim",
            target_commitment_id=commitments[5].id,
            confidence_score=0.60,
            message_content="Hey David, the roadmap update was due a couple of days ago. Quick pulse check — still planning to get to it, or should we flag it?",
        ),
        AgentAction(
            action_type=AgentActionType.ESCALATE,
            agent_name="escalation",
            description="ESCALATION: 'Complete API performance audit' is blocking David's query optimization work",
            target_person="Priya Patel",
            target_commitment_id=commitments[1].id,
            confidence_score=0.55,
            escalate_to="Sarah Chen",
            message_content="Escalation: Priya's API performance audit is blocking David's query optimization. The audit was due yesterday. This needs attention to unblock the downstream work.",
        ),
    ]

    for action in actions:
        db.create_agent_action(action)
    print(f"  ✅ Created {len(actions)} pending agent actions")

    # --- Final Stats ---
    stats = db.get_stats()
    print(f"\n  📊 Graph Statistics:")
    print(f"     People:           {stats.get('people', 0)}")
    print(f"     Commitments:      {stats.get('commitments', 0)}")
    print(f"     Decisions:        {stats.get('decisions', 0)}")
    print(f"     Pending Actions:  {stats.get('pending_approvals', 0)}")

    print("\n✅ Demo data seeded successfully!")
    print("\n🌐 Open the dashboard: http://localhost:8501")
    print("📡 API documentation: http://localhost:8000/docs")


if __name__ == "__main__":
    seed_demo_data()
