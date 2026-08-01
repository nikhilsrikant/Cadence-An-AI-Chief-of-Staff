"""
Cadence - API Routes
All REST endpoints for the Cadence backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.extraction.extractor import get_extractor
from backend.graph.database import get_db
from backend.models.schemas import (
    AgentAction,
    ApprovalRequest,
    ApprovalStatus,
    Commitment,
    CommitmentStatus,
    Conflict,
    DashboardItem,
    Decision,
    ExtractionResult,
    HealthResponse,
    Person,
    TranscriptInput,
)
from backend.utils.logger import logger

router = APIRouter()


# =============================================================================
# Health & Status
# =============================================================================


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health: Neo4j connectivity, agent status, stats."""
    db = get_db()
    connected = db.is_connected()

    stats = {"commitments": 0, "pending_approvals": 0}
    if connected:
        try:
            stats = db.get_stats()
        except Exception:
            pass

    return HealthResponse(
        status="healthy" if connected else "degraded",
        neo4j_connected=connected,
        agents_running=True,
        pending_approvals=stats.get("pending_approvals", 0),
        total_commitments=stats.get("commitments", 0),
    )


@router.get("/stats", tags=["System"])
async def get_statistics():
    """Get overall graph statistics."""
    db = get_db()
    if not db.is_connected():
        return {"commitments": 0, "people": 0, "decisions": 0, "pending_approvals": 0}
    return db.get_stats()


# =============================================================================
# Ingestion & Extraction
# =============================================================================


@router.post("/ingest", response_model=ExtractionResult, tags=["Ingestion"])
async def ingest_transcript(input_data: TranscriptInput):
    """
    Ingest a meeting transcript, Slack thread, or calendar invite.
    Extracts commitments and decisions, stores them in the knowledge graph.
    """
    logger.info(f"Ingesting {input_data.source_type.value}: {len(input_data.text)} chars")

    # Extract commitments and decisions
    extractor = get_extractor()
    result = extractor.extract(input_data)

    # Store in graph
    db = get_db()
    if db.is_connected():
        for commitment in result.commitments:
            try:
                db.create_commitment(commitment)
                logger.info(f"Stored commitment: {commitment.title} -> {commitment.owner_name}")
            except Exception as e:
                logger.error(f"Failed to store commitment: {e}")

        for decision in result.decisions:
            try:
                db.create_decision(decision)
                logger.info(f"Stored decision: {decision.title}")
            except Exception as e:
                logger.error(f"Failed to store decision: {e}")

    return result


# =============================================================================
# Commitments
# =============================================================================


@router.get("/commitments", response_model=List[dict], tags=["Commitments"])
async def list_commitments(
    owner: Optional[str] = Query(None, description="Filter by owner name"),
    status: Optional[CommitmentStatus] = Query(None, description="Filter by status"),
):
    """Get all commitments, optionally filtered by owner or status."""
    db = get_db()
    if not db.is_connected():
        return []

    if owner:
        commitments = db.get_commitments_by_owner(owner)
    else:
        commitments = db.get_all_commitments()

    if status:
        commitments = [c for c in commitments if c.get("status") == status.value]

    return commitments


@router.get("/commitments/{commitment_id}", tags=["Commitments"])
async def get_commitment(commitment_id: str):
    """Get a single commitment by ID."""
    db = get_db()
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database not available")

    commitment = db.get_commitment(commitment_id)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return commitment


@router.patch("/commitments/{commitment_id}/status", tags=["Commitments"])
async def update_commitment_status(commitment_id: str, status: CommitmentStatus):
    """Update the status of a commitment."""
    db = get_db()
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database not available")

    db.update_commitment_status(commitment_id, status)
    return {"message": f"Commitment {commitment_id} updated to {status.value}"}


# =============================================================================
# Decisions
# =============================================================================


@router.get("/decisions", response_model=List[dict], tags=["Decisions"])
async def list_decisions():
    """Get all decisions from the knowledge graph."""
    db = get_db()
    if not db.is_connected():
        return []
    return db.get_all_decisions()


# =============================================================================
# Conflicts
# =============================================================================


@router.get("/conflicts", tags=["Conflicts"])
async def detect_conflicts():
    """
    Detect all conflicts in the graph:
    - Schedule conflicts (same person, same day)
    - Overloaded people (too many active commitments)
    - Blocking chains (items blocking multiple downstream tasks)
    """
    db = get_db()
    if not db.is_connected():
        return {"schedule_conflicts": [], "overloaded": [], "blocking_chains": []}

    schedule_conflicts = db.detect_schedule_conflicts()
    overloaded = db.detect_overloaded_people()
    blocking_chains = db.detect_blocking_chains()

    return {
        "schedule_conflicts": schedule_conflicts,
        "overloaded": overloaded,
        "blocking_chains": blocking_chains,
        "total_conflicts": len(schedule_conflicts) + len(overloaded) + len(blocking_chains),
    }


# =============================================================================
# Dashboard
# =============================================================================


@router.get("/dashboard", tags=["Dashboard"])
async def get_dashboard(
    person: Optional[str] = Query(None, description="Filter dashboard for a specific person"),
):
    """
    Get the decision dashboard: prioritized view of items needing action,
    ranked by urgency, impact, and blocking count.
    """
    db = get_db()
    if not db.is_connected():
        return {"items": [], "summary": {}}

    items = db.get_dashboard_items(person_name=person)
    pending_actions = db.get_pending_actions()

    return {
        "items": items,
        "pending_approvals": len(pending_actions),
        "summary": {
            "total_items": len(items),
            "high_urgency": len([i for i in items if i.get("urgency_score", 0) >= 0.8]),
            "blocking_items": len([i for i in items if i.get("blocking_count", 0) > 0]),
        },
    }


# =============================================================================
# Approval Gate
# =============================================================================


@router.get("/approvals", response_model=List[dict], tags=["Approvals"])
async def list_pending_approvals():
    """Get all agent actions awaiting human approval."""
    db = get_db()
    if not db.is_connected():
        return []
    return db.get_pending_actions()


@router.post("/approvals/review", tags=["Approvals"])
async def review_approval(request: ApprovalRequest):
    """Approve or reject an agent-proposed action."""
    db = get_db()
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database not available")

    status = ApprovalStatus.APPROVED if request.approved else ApprovalStatus.REJECTED
    executed_at = datetime.utcnow() if request.approved else None

    db.update_action_status(request.action_id, status, executed_at)

    action_verb = "approved" if request.approved else "rejected"
    logger.info(f"Action {request.action_id} {action_verb}")

    return {
        "message": f"Action {action_verb}",
        "action_id": request.action_id,
        "status": status.value,
        "executed_at": executed_at.isoformat() if executed_at else None,
    }


# =============================================================================
# Agents
# =============================================================================


@router.post("/agents/run", tags=["Agents"])
async def trigger_agents():
    """
    Manually trigger all orchestration agents:
    - Scheduler: detects conflicts and proposes reschedules
    - Follow-up: nudges owners of stale commitments
    - Escalation: escalates critically overdue items
    """
    from backend.agents.orchestrator import run_all_agents

    results = run_all_agents()
    return {
        "message": "Agent run complete",
        "results": results,
    }


@router.post("/agents/scheduler", tags=["Agents"])
async def trigger_scheduler():
    """Manually trigger only the scheduler agent."""
    from backend.agents.scheduler_agent import SchedulerAgent

    agent = SchedulerAgent()
    actions = agent.run()
    return {"agent": "scheduler", "actions_proposed": len(actions), "actions": [a.model_dump() for a in actions]}


@router.post("/agents/followup", tags=["Agents"])
async def trigger_followup():
    """Manually trigger only the follow-up agent."""
    from backend.agents.followup_agent import FollowUpAgent

    agent = FollowUpAgent()
    actions = agent.run()
    return {"agent": "followup", "actions_proposed": len(actions), "actions": [a.model_dump() for a in actions]}


@router.post("/agents/escalation", tags=["Agents"])
async def trigger_escalation():
    """Manually trigger only the escalation agent."""
    from backend.agents.escalation_agent import EscalationAgent

    agent = EscalationAgent()
    actions = agent.run()
    return {"agent": "escalation", "actions_proposed": len(actions), "actions": [a.model_dump() for a in actions]}


# =============================================================================
# People
# =============================================================================


@router.get("/people", tags=["People"])
async def list_people():
    """Get all people in the knowledge graph."""
    db = get_db()
    if not db.is_connected():
        return []

    query = "MATCH (p:Person) RETURN p ORDER BY p.name"
    with db.get_session() as session:
        result = session.run(query)
        return [dict(record["p"]) for record in result]


@router.get("/people/{name}/commitments", tags=["People"])
async def get_person_commitments(name: str):
    """Get all commitments owned by a specific person."""
    db = get_db()
    if not db.is_connected():
        return []
    return db.get_commitments_by_owner(name)


# =============================================================================
# Graph
# =============================================================================


@router.get("/graph/export", tags=["Graph"])
async def export_graph():
    """Export the full knowledge graph for visualization."""
    db = get_db()
    if not db.is_connected():
        return {"nodes": [], "edges": []}

    nodes_query = """
    MATCH (n)
    RETURN labels(n)[0] as label, properties(n) as props
    """
    edges_query = """
    MATCH (a)-[r]->(b)
    RETURN a.id as source, b.id as target, type(r) as relationship
    """

    nodes = []
    edges = []

    with db.get_session() as session:
        result = session.run(nodes_query)
        for record in result:
            node_data = record["props"]
            node_data["_label"] = record["label"]
            nodes.append(node_data)

        result = session.run(edges_query)
        for record in result:
            edges.append({
                "source": record["source"],
                "target": record["target"],
                "relationship": record["relationship"],
            })

    return {"nodes": nodes, "edges": edges}


@router.post("/graph/reset", tags=["Graph"])
async def reset_graph():
    """Reset/clear all graph data. USE WITH CAUTION."""
    db = get_db()
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database not available")

    db.clear_all()
    db.init_schema()
    return {"message": "Graph cleared and schema re-initialized"}
