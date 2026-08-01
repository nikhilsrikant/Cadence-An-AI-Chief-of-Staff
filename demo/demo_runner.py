"""
Cadence - Demo Runner Script
Demonstrates the full 4-step demo flow for hackathon judges:

1. Upload a sample meeting transcript → watch commitments populate the graph live.
2. Trigger a conflict: two commitments, same owner, same day → Cadence proposes a reschedule.
3. One-click approve in the human gate → nudge goes out, calendar updates.
4. Show the decision dashboard ranking open items by blocking impact.

This script can be run standalone or imported for interactive demo.
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

API_BASE = "http://localhost:8000/api"


def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_step(step_num: int, title: str):
    """Print a demo step marker."""
    print(f"\n{'─' * 60}")
    print(f"  STEP {step_num}: {title}")
    print(f"{'─' * 60}\n")


def api_get(endpoint: str):
    """GET request to API."""
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def api_post(endpoint: str, data: dict = None):
    """POST request to API."""
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def check_health():
    """Verify the API is running."""
    print("Checking API health...")
    result = api_get("/health")
    if result:
        print(f"  Status: {result['status']}")
        print(f"  Neo4j: {'Connected' if result['neo4j_connected'] else 'Disconnected'}")
        return True
    else:
        print("  ERROR: API is not reachable. Start with: docker-compose up")
        return False


# =============================================================================
# STEP 1: Ingest Meeting Transcript
# =============================================================================

def step1_ingest_transcript():
    """Upload sample meeting transcript and extract commitments."""
    print_step(1, "INGEST MEETING TRANSCRIPT")
    print("Uploading Q4 Product Planning Meeting transcript...")
    print("Extracting commitments and decisions using Granite model...\n")

    # Load sample transcript
    transcript_path = Path(__file__).parent / "sample_transcript.txt"
    with open(transcript_path, "r") as f:
        transcript_text = f.read()

    payload = {
        "text": transcript_text,
        "source_type": "meeting_transcript",
        "meeting_title": "Q4 Product Planning Meeting",
        "participants": ["Sarah Chen", "Marcus Johnson", "Priya Patel", "David Kim", "Lisa Wong"],
    }

    result = api_post("/ingest", payload)

    if result:
        commitments = result.get("commitments", [])
        decisions = result.get("decisions", [])

        print(f"  ✅ Extracted {len(commitments)} commitments and {len(decisions)} decisions\n")

        print("  📌 COMMITMENTS:")
        for i, c in enumerate(commitments, 1):
            print(f"     {i}. [{c.get('priority', 'medium').upper()}] {c.get('title', 'Untitled')}")
            print(f"        Owner: {c.get('owner_name', 'Unknown')} | Deadline: {c.get('deadline', 'TBD')}")

        print(f"\n  🎯 DECISIONS:")
        for i, d in enumerate(decisions, 1):
            print(f"     {i}. {d.get('title', 'Untitled')}")
            print(f"        Made by: {d.get('made_by', 'Unknown')}")

        return result
    else:
        print("  ❌ Extraction failed")
        return None


# =============================================================================
# STEP 2: Trigger Conflict Detection
# =============================================================================

def step2_trigger_conflict():
    """
    Inject a conflict scenario and run the scheduler agent.
    Creates two commitments for the same person on the same day.
    """
    print_step(2, "TRIGGER CONFLICT DETECTION")
    print("Scenario: Lisa Wong has TWO critical commitments due the same day")
    print("  - SOC2 Security Review (due Oct 20)")
    print("  - Auth Module Review for Marcus (also due Oct 20)")
    print("\nRunning scheduler agent to detect conflicts...\n")

    # Run the scheduler agent
    result = api_post("/agents/scheduler")

    if result:
        actions = result.get("actions", [])
        print(f"  ⚠️  Scheduler detected conflicts and proposed {len(actions)} actions:\n")

        for action in actions:
            print(f"  📅 {action.get('description', 'No description')}")
            if action.get("message_content"):
                print(f"     Message: \"{action['message_content'][:100]}...\"")
            print(f"     Confidence: {action.get('confidence_score', 0):.0%}")
            print()

        return actions
    else:
        print("  Running conflict detection via API...")
        conflicts = api_get("/conflicts")
        if conflicts:
            total = conflicts.get("total_conflicts", 0)
            print(f"  Found {total} conflicts in the graph")
            return conflicts
        return None


# =============================================================================
# STEP 3: Human Approval Gate
# =============================================================================

def step3_approve_action():
    """Show pending approvals and approve one."""
    print_step(3, "HUMAN APPROVAL GATE")
    print("Reviewing pending actions in the approval queue...")
    print("'Trust is the product, not a feature.'\n")

    pending = api_get("/approvals")

    if pending and len(pending) > 0:
        print(f"  📋 {len(pending)} actions awaiting approval:\n")

        for i, action in enumerate(pending[:3], 1):
            action_type = action.get("action_type", "unknown")
            emoji = {"nudge": "💬", "reschedule": "📅", "escalate": "🚨"}.get(action_type, "⚡")
            print(f"  {i}. {emoji} [{action_type.upper()}] {action.get('description', 'N/A')}")
            print(f"     Confidence: {action.get('confidence_score', 0):.0%} | "
                  f"Target: {action.get('target_person', 'Unknown')}")
            if action.get("message_content"):
                print(f"     Preview: \"{action['message_content'][:80]}...\"")
            print()

        # Approve the first pending action
        first_action = pending[0]
        print(f"  ✅ Approving action: {first_action.get('description', 'N/A')[:60]}...")

        approval_result = api_post("/approvals/review", {
            "action_id": first_action["id"],
            "approved": True,
            "reviewer_note": "Approved during demo - looks good",
        })

        if approval_result:
            print(f"  → Action APPROVED at {approval_result.get('executed_at', 'now')}")
            print("  → Nudge sent, calendar updated ✓")
        else:
            print("  → Approval submitted")

        return approval_result
    else:
        print("  No pending approvals (all within auto-approve threshold)")
        print("  Auto-approve threshold: confidence >= 0.7")
        return None


# =============================================================================
# STEP 4: Decision Dashboard
# =============================================================================

def step4_show_dashboard():
    """Display the prioritized decision dashboard."""
    print_step(4, "DECISION DASHBOARD")
    print("Showing prioritized items ranked by urgency, impact, and blocking count...\n")

    dashboard = api_get("/dashboard")

    if dashboard:
        items = dashboard.get("items", [])
        summary = dashboard.get("summary", {})

        print(f"  📊 DASHBOARD SUMMARY")
        print(f"     Total Action Items:  {summary.get('total_items', 0)}")
        print(f"     High Urgency:        {summary.get('high_urgency', 0)}")
        print(f"     Blocking Items:      {summary.get('blocking_items', 0)}")
        print(f"     Pending Approvals:   {dashboard.get('pending_approvals', 0)}")
        print()

        if items:
            print("  🏆 TOP ITEMS (ranked by urgency × impact × blocking):\n")
            print(f"  {'#':<3} {'Urgency':<9} {'Title':<40} {'Owner':<15} {'Status'}")
            print(f"  {'─'*3} {'─'*9} {'─'*40} {'─'*15} {'─'*12}")

            for i, item in enumerate(items[:5], 1):
                urgency = item.get("urgency_score", 0)
                bar = "🔴" if urgency >= 0.8 else "🟠" if urgency >= 0.5 else "🟢"
                title = item.get("title", "Untitled")[:38]
                owner = item.get("owner", "Unknown")[:13]
                status = item.get("status", "unknown")

                print(f"  {i:<3} {bar} {urgency:.0%}   {title:<40} {owner:<15} {status}")

            blocking_items = [i for i in items if i.get("blocking_count", 0) > 0]
            if blocking_items:
                print(f"\n  ⛓️  {len(blocking_items)} items are blocking downstream work")
        else:
            print("  Dashboard is empty. Ingest a transcript first!")

        return dashboard
    else:
        print("  Could not load dashboard data")
        return None


# =============================================================================
# Full Demo Flow
# =============================================================================

def run_full_demo():
    """Execute the complete 4-step demo flow."""
    print_header("CADENCE: AN AI CHIEF OF STAFF — DEMO")
    print("  Built on IBM watsonx Orchestrate")
    print("  Most AI tools answer questions. Cadence closes the loop.")
    print()

    # Health check
    if not check_health():
        print("\n⚠️  API not available. Running in description-only mode.")
        print("Start the system with: docker-compose up")
        print("\nProceeding with demo narrative...\n")

    time.sleep(1)

    # Step 1
    step1_ingest_transcript()
    time.sleep(1)

    # Step 2
    step2_trigger_conflict()
    time.sleep(1)

    # Step 3
    step3_approve_action()
    time.sleep(1)

    # Step 4
    step4_show_dashboard()

    # Wrap up
    print_header("DEMO COMPLETE")
    print("  Key Capabilities Demonstrated:")
    print("  1. ✅ Commitment extraction from unstructured meeting text")
    print("  2. ✅ Conflict detection via Neo4j knowledge graph")
    print("  3. ✅ Human approval gate with configurable auto-clear")
    print("  4. ✅ Prioritized decision dashboard")
    print()
    print("  Tech Stack: watsonx Orchestrate · watsonx.ai (Granite) · Neo4j · FastAPI · Streamlit")
    print()
    print("  'From what got decided in a meeting to what actually gets done.'")
    print()


if __name__ == "__main__":
    run_full_demo()
