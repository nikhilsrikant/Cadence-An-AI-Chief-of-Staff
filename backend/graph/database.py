"""
Cadence - Neo4j Database Driver & Operations
Provides connection management and CRUD operations for the knowledge graph.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable

from backend.graph.schema import SCHEMA_CONSTRAINTS, SCHEMA_INDEXES
from backend.models.schemas import (
    Commitment, CommitmentStatus, Decision, Person, Conflict,
    AgentAction, ApprovalStatus, Priority, DashboardItem,
)
from backend.utils.logger import logger


class Neo4jConnection:
    """Manages Neo4j driver lifecycle and provides graph operations."""

    def __init__(self, uri: str, user: str, password: str):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: Optional[Driver] = None

    def connect(self) -> None:
        """Establish connection to Neo4j."""
        try:
            self._driver = GraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
            self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self._uri}")
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self) -> None:
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")

    @property
    def driver(self) -> Driver:
        if not self._driver:
            raise RuntimeError("Neo4j not connected. Call connect() first.")
        return self._driver

    def get_session(self) -> Session:
        return self.driver.session()

    def is_connected(self) -> bool:
        """Check if Neo4j is reachable."""
        try:
            if self._driver:
                self._driver.verify_connectivity()
                return True
        except Exception:
            pass
        return False

    # --- Schema Initialization ---

    def init_schema(self) -> None:
        """Create constraints and indexes."""
        with self.get_session() as session:
            for constraint in SCHEMA_CONSTRAINTS:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.debug(f"Constraint may already exist: {e}")
            for index in SCHEMA_INDEXES:
                try:
                    session.run(index)
                except Exception as e:
                    logger.debug(f"Index may already exist: {e}")
        logger.info("Neo4j schema initialized")

    # --- Person Operations ---

    def upsert_person(self, person: Person) -> Person:
        """Create or update a Person node."""
        query = """
        MERGE (p:Person {name: $name})
        ON CREATE SET p.id = $id, p.email = $email, p.role = $role, p.team = $team
        ON MATCH SET p.email = COALESCE($email, p.email),
                     p.role = COALESCE($role, p.role),
                     p.team = COALESCE($team, p.team)
        RETURN p
        """
        with self.get_session() as session:
            session.run(query, **person.model_dump())
        return person

    def get_person_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a person node by name."""
        query = "MATCH (p:Person {name: $name}) RETURN p"
        with self.get_session() as session:
            result = session.run(query, name=name)
            record = result.single()
            return dict(record["p"]) if record else None

    # --- Commitment Operations ---

    def create_commitment(self, commitment: Commitment) -> Commitment:
        """Create a Commitment node and link it to the owner."""
        query = """
        MERGE (p:Person {name: $owner_name})
        ON CREATE SET p.id = randomUUID()
        CREATE (c:Commitment {
            id: $id,
            title: $title,
            description: $description,
            owner_name: $owner_name,
            deadline: $deadline,
            status: $status,
            priority: $priority,
            source_type: $source_type,
            source_id: $source_id,
            created_at: $created_at,
            updated_at: $updated_at,
            meeting_title: $meeting_title,
            blocking_count: 0
        })
        CREATE (p)-[:OWNS]->(c)
        RETURN c
        """
        params = commitment.model_dump()
        params["status"] = commitment.status.value
        params["priority"] = commitment.priority.value
        params["source_type"] = commitment.source_type.value
        params["deadline"] = commitment.deadline.isoformat() if commitment.deadline else None
        params["created_at"] = commitment.created_at.isoformat()
        params["updated_at"] = commitment.updated_at.isoformat()

        with self.get_session() as session:
            session.run(query, **params)

        # Create dependency relationships
        if commitment.dependencies:
            self._link_dependencies(commitment.id, commitment.dependencies)

        return commitment

    def _link_dependencies(self, commitment_id: str, dependency_ids: List[str]) -> None:
        """Create DEPENDS_ON relationships."""
        query = """
        MATCH (c:Commitment {id: $commitment_id})
        MATCH (dep:Commitment {id: $dep_id})
        MERGE (c)-[:DEPENDS_ON]->(dep)
        """
        with self.get_session() as session:
            for dep_id in dependency_ids:
                session.run(query, commitment_id=commitment_id, dep_id=dep_id)

    def get_commitment(self, commitment_id: str) -> Optional[Dict[str, Any]]:
        """Get a single commitment by ID."""
        query = "MATCH (c:Commitment {id: $id}) RETURN c"
        with self.get_session() as session:
            result = session.run(query, id=commitment_id)
            record = result.single()
            return dict(record["c"]) if record else None

    def get_all_commitments(self) -> List[Dict[str, Any]]:
        """Get all commitments."""
        query = """
        MATCH (p:Person)-[:OWNS]->(c:Commitment)
        RETURN c, p.name as owner_name
        ORDER BY c.deadline ASC
        """
        with self.get_session() as session:
            result = session.run(query)
            return [dict(record["c"]) for record in result]

    def get_commitments_by_owner(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get all commitments for a specific person."""
        query = """
        MATCH (p:Person {name: $owner_name})-[:OWNS]->(c:Commitment)
        RETURN c
        ORDER BY c.deadline ASC
        """
        with self.get_session() as session:
            result = session.run(query, owner_name=owner_name)
            return [dict(record["c"]) for record in result]

    def update_commitment_status(self, commitment_id: str, status: CommitmentStatus) -> None:
        """Update the status of a commitment."""
        query = """
        MATCH (c:Commitment {id: $id})
        SET c.status = $status, c.updated_at = $updated_at
        """
        with self.get_session() as session:
            session.run(
                query,
                id=commitment_id,
                status=status.value,
                updated_at=datetime.utcnow().isoformat(),
            )

    # --- Decision Operations ---

    def create_decision(self, decision: Decision) -> Decision:
        """Create a Decision node."""
        query = """
        MERGE (p:Person {name: $made_by})
        ON CREATE SET p.id = randomUUID()
        CREATE (d:Decision {
            id: $id,
            title: $title,
            description: $description,
            made_by: $made_by,
            source_type: $source_type,
            source_id: $source_id,
            created_at: $created_at
        })
        CREATE (p)-[:MADE_DECISION]->(d)
        RETURN d
        """
        params = decision.model_dump()
        params["source_type"] = decision.source_type.value
        params["created_at"] = decision.created_at.isoformat()

        with self.get_session() as session:
            session.run(query, **params)
        return decision

    def get_all_decisions(self) -> List[Dict[str, Any]]:
        """Get all decisions."""
        query = "MATCH (d:Decision) RETURN d ORDER BY d.created_at DESC"
        with self.get_session() as session:
            result = session.run(query)
            return [dict(record["d"]) for record in result]

    # --- Conflict Detection ---

    def detect_schedule_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect schedule conflicts: same owner, same deadline day, multiple commitments.
        """
        query = """
        MATCH (p:Person)-[:OWNS]->(c:Commitment)
        WHERE c.status IN ['pending', 'accepted', 'in_progress']
          AND c.deadline IS NOT NULL
        WITH p, date(c.deadline) as due_date, collect(c) as commitments
        WHERE size(commitments) > 1
        RETURN p.name as person, due_date,
               [c IN commitments | {id: c.id, title: c.title, deadline: c.deadline, priority: c.priority}] as conflicts
        """
        with self.get_session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def detect_overloaded_people(self, threshold: int = 3) -> List[Dict[str, Any]]:
        """Detect people with too many active commitments."""
        query = """
        MATCH (p:Person)-[:OWNS]->(c:Commitment)
        WHERE c.status IN ['pending', 'accepted', 'in_progress']
        WITH p, collect(c) as active_commitments
        WHERE size(active_commitments) >= $threshold
        RETURN p.name as person, size(active_commitments) as load,
               [c IN active_commitments | {id: c.id, title: c.title, deadline: c.deadline}] as commitments
        """
        with self.get_session() as session:
            result = session.run(query, threshold=threshold)
            return [dict(record) for record in result]

    def detect_blocking_chains(self) -> List[Dict[str, Any]]:
        """Detect commitments blocking multiple downstream items."""
        query = """
        MATCH (downstream:Commitment)-[:DEPENDS_ON]->(blocker:Commitment)
        WHERE blocker.status IN ['pending', 'accepted', 'in_progress']
        WITH blocker, count(downstream) as blocking_count
        WHERE blocking_count > 0
        SET blocker.blocking_count = blocking_count
        RETURN blocker.id as id, blocker.title as title,
               blocker.owner_name as owner, blocker.deadline as deadline,
               blocking_count
        ORDER BY blocking_count DESC
        """
        with self.get_session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def detect_stale_commitments(self, stale_hours: int = 48) -> List[Dict[str, Any]]:
        """Detect commitments that haven't been updated in stale_hours."""
        query = """
        MATCH (p:Person)-[:OWNS]->(c:Commitment)
        WHERE c.status IN ['pending', 'accepted']
          AND duration.between(datetime(c.updated_at), datetime()).hours > $stale_hours
        RETURN c.id as id, c.title as title, p.name as owner,
               c.deadline as deadline, c.status as status, c.updated_at as last_updated
        """
        with self.get_session() as session:
            result = session.run(query, stale_hours=stale_hours)
            return [dict(record) for record in result]

    # --- Agent Action Operations ---

    def create_agent_action(self, action: AgentAction) -> AgentAction:
        """Store an agent's proposed action."""
        query = """
        CREATE (a:AgentAction {
            id: $id,
            action_type: $action_type,
            agent_name: $agent_name,
            description: $description,
            target_person: $target_person,
            target_commitment_id: $target_commitment_id,
            proposed_at: $proposed_at,
            approval_status: $approval_status,
            confidence_score: $confidence_score,
            message_content: $message_content,
            proposed_new_deadline: $proposed_new_deadline,
            escalate_to: $escalate_to
        })
        RETURN a
        """
        params = action.model_dump()
        params["action_type"] = action.action_type.value
        params["approval_status"] = action.approval_status.value
        params["proposed_at"] = action.proposed_at.isoformat()
        params["proposed_new_deadline"] = (
            action.proposed_new_deadline.isoformat() if action.proposed_new_deadline else None
        )
        params.pop("executed_at", None)

        with self.get_session() as session:
            session.run(query, **params)

        # Link to target commitment if specified
        if action.target_commitment_id:
            link_query = """
            MATCH (a:AgentAction {id: $action_id})
            MATCH (c:Commitment {id: $commitment_id})
            MERGE (a)-[:TARGETS]->(c)
            """
            with self.get_session() as session:
                session.run(
                    link_query,
                    action_id=action.id,
                    commitment_id=action.target_commitment_id,
                )

        return action

    def get_pending_actions(self) -> List[Dict[str, Any]]:
        """Get all actions awaiting approval."""
        query = """
        MATCH (a:AgentAction)
        WHERE a.approval_status = 'pending'
        RETURN a
        ORDER BY a.proposed_at ASC
        """
        with self.get_session() as session:
            result = session.run(query)
            return [dict(record["a"]) for record in result]

    def update_action_status(
        self, action_id: str, status: ApprovalStatus, executed_at: Optional[datetime] = None
    ) -> None:
        """Update approval status of an agent action."""
        query = """
        MATCH (a:AgentAction {id: $id})
        SET a.approval_status = $status
        """
        params: Dict[str, Any] = {"id": action_id, "status": status.value}
        if executed_at:
            query += ", a.executed_at = $executed_at"
            params["executed_at"] = executed_at.isoformat()

        with self.get_session() as session:
            session.run(query, **params)

    # --- Dashboard Queries ---

    def get_dashboard_items(self, person_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get prioritized dashboard items: commitments needing action,
        ranked by urgency, impact, and blocking count.
        """
        where_clause = ""
        params: Dict[str, Any] = {}
        if person_name:
            where_clause = "WHERE p.name = $person_name"
            params["person_name"] = person_name

        query = f"""
        MATCH (p:Person)-[:OWNS]->(c:Commitment)
        {where_clause}
        WITH c, p,
             CASE
                WHEN c.status = 'overdue' THEN 1.0
                WHEN c.status = 'escalated' THEN 0.9
                WHEN c.deadline IS NOT NULL AND
                     duration.between(datetime(), datetime(c.deadline)).days < 2 THEN 0.8
                WHEN c.status = 'pending' THEN 0.5
                ELSE 0.3
             END as urgency,
             CASE
                WHEN c.priority = 'critical' THEN 1.0
                WHEN c.priority = 'high' THEN 0.75
                WHEN c.priority = 'medium' THEN 0.5
                ELSE 0.25
             END as impact
        WHERE c.status IN ['pending', 'accepted', 'in_progress', 'overdue', 'escalated']
        RETURN c.id as id, c.title as title, 'commitment' as type,
               urgency as urgency_score, impact as impact_score,
               COALESCE(c.blocking_count, 0) as blocking_count,
               p.name as owner, c.deadline as deadline, c.status as status
        ORDER BY urgency DESC, impact DESC, blocking_count DESC
        """
        with self.get_session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    # --- Graph Statistics ---

    def get_stats(self) -> Dict[str, int]:
        """Get overall graph statistics."""
        query = """
        MATCH (c:Commitment) WITH count(c) as commitments
        MATCH (p:Person) WITH commitments, count(p) as people
        MATCH (d:Decision) WITH commitments, people, count(d) as decisions
        OPTIONAL MATCH (a:AgentAction {approval_status: 'pending'})
        WITH commitments, people, decisions, count(a) as pending_approvals
        RETURN commitments, people, decisions, pending_approvals
        """
        with self.get_session() as session:
            result = session.run(query)
            record = result.single()
            if record:
                return dict(record)
        return {"commitments": 0, "people": 0, "decisions": 0, "pending_approvals": 0}

    def clear_all(self) -> None:
        """Clear all data from the graph (for testing/demo reset)."""
        with self.get_session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.warning("All graph data cleared")


# --- Singleton Instance ---

_db_instance: Optional[Neo4jConnection] = None


def get_db() -> Neo4jConnection:
    """Get the global Neo4j connection instance."""
    global _db_instance
    if _db_instance is None:
        from config.settings import settings
        _db_instance = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
    return _db_instance


def init_db() -> Neo4jConnection:
    """Initialize and return the database connection."""
    db = get_db()
    db.connect()
    db.init_schema()
    return db
