"""
Cadence - Neo4j Graph Schema
Defines the Cypher constraints, indexes, and schema initialization.
"""

# Node Labels:
#   - Person: team members
#   - Commitment: structured commitment extracted from communications
#   - Decision: a decision made in a meeting or thread
#   - Meeting: source meeting/thread
#   - Conflict: detected scheduling or resource conflict
#   - AgentAction: actions proposed by orchestration agents

# Relationship Types:
#   - OWNS: Person -> Commitment
#   - MADE_DECISION: Person -> Decision
#   - ACCEPTED_DECISION: Person -> Decision
#   - DEPENDS_ON: Commitment -> Commitment
#   - DERIVED_FROM: Commitment -> Decision
#   - DISCUSSED_IN: Commitment -> Meeting / Decision -> Meeting
#   - BLOCKS: Commitment -> Commitment
#   - CONFLICTS_WITH: Commitment -> Commitment
#   - TARGETS: AgentAction -> Commitment
#   - AFFECTS: Conflict -> Person
#   - INVOLVES: Conflict -> Commitment

SCHEMA_CONSTRAINTS = [
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT commitment_id IF NOT EXISTS FOR (c:Commitment) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT conflict_id IF NOT EXISTS FOR (cf:Conflict) REQUIRE cf.id IS UNIQUE",
    "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:AgentAction) REQUIRE a.id IS UNIQUE",
]

SCHEMA_INDEXES = [
    "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
    "CREATE INDEX commitment_status_idx IF NOT EXISTS FOR (c:Commitment) ON (c.status)",
    "CREATE INDEX commitment_deadline_idx IF NOT EXISTS FOR (c:Commitment) ON (c.deadline)",
    "CREATE INDEX commitment_owner_idx IF NOT EXISTS FOR (c:Commitment) ON (c.owner_name)",
    "CREATE INDEX decision_title_idx IF NOT EXISTS FOR (d:Decision) ON (d.title)",
    "CREATE INDEX action_status_idx IF NOT EXISTS FOR (a:AgentAction) ON (a.approval_status)",
    "CREATE INDEX conflict_resolved_idx IF NOT EXISTS FOR (cf:Conflict) ON (cf.resolved)",
]
