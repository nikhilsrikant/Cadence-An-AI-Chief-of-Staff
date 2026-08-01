"""
Cadence - Streamlit Decision Dashboard
A daily "what needs a decision from you" view, ranked by urgency,
impact, and how many downstream items it's blocking.
"""

import streamlit as st
import requests
import json
import os
import re
from datetime import datetime

# --- Configuration ---
API_BASE = "http://localhost:8000/api"

# Demo mode: use mock data when backend is not available
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"


# --- Mock Data for Standalone Demo ---
MOCK_STATS = {
    "commitments": 9,
    "people": 5,
    "decisions": 3,
    "pending_approvals": 3,
}

MOCK_DASHBOARD = {
    "items": [
        {"id": "c1", "title": "Complete API performance audit", "type": "commitment", "urgency_score": 1.0, "impact_score": 0.75, "blocking_count": 1, "owner": "Priya Patel", "deadline": "2024-10-16", "status": "overdue"},
        {"id": "c2", "title": "Complete SOC2 security compliance review", "type": "commitment", "urgency_score": 0.9, "impact_score": 1.0, "blocking_count": 0, "owner": "Lisa Wong", "deadline": "2024-10-20", "status": "in_progress"},
        {"id": "c3", "title": "Optimize database queries for slow endpoints", "type": "commitment", "urgency_score": 0.8, "impact_score": 0.75, "blocking_count": 0, "owner": "David Kim", "deadline": "2024-10-17", "status": "pending"},
        {"id": "c4", "title": "Complete React migration plan", "type": "commitment", "urgency_score": 0.5, "impact_score": 0.75, "blocking_count": 0, "owner": "Marcus Johnson", "deadline": "2024-10-22", "status": "in_progress"},
        {"id": "c5", "title": "Update roadmap to reflect Q1 mobile postponement", "type": "commitment", "urgency_score": 1.0, "impact_score": 0.5, "blocking_count": 0, "owner": "David Kim", "deadline": "2024-10-13", "status": "overdue"},
        {"id": "c6", "title": "Prepare Q4 exec presentation", "type": "commitment", "urgency_score": 0.5, "impact_score": 0.75, "blocking_count": 0, "owner": "Sarah Chen", "deadline": "2024-10-25", "status": "pending"},
        {"id": "c7", "title": "Review auth module for React migration", "type": "commitment", "urgency_score": 0.5, "impact_score": 0.5, "blocking_count": 0, "owner": "Lisa Wong", "deadline": "2024-10-20", "status": "pending"},
        {"id": "c8", "title": "Submit Q4 section summaries to Sarah", "type": "commitment", "urgency_score": 0.5, "impact_score": 0.5, "blocking_count": 1, "owner": "Marcus Johnson", "deadline": "2024-10-23", "status": "pending"},
        {"id": "c9", "title": "Review updated OKRs and provide sign-off", "type": "commitment", "urgency_score": 0.5, "impact_score": 0.5, "blocking_count": 0, "owner": "Priya Patel", "deadline": "2024-10-19", "status": "pending"},
    ],
    "pending_approvals": 3,
    "summary": {"total_items": 9, "high_urgency": 3, "blocking_items": 2},
}

MOCK_COMMITMENTS = MOCK_DASHBOARD["items"]


MOCK_CONFLICTS = {
    "schedule_conflicts": [
        {"person": "Lisa Wong", "due_date": "2024-10-20", "conflicts": [
            {"id": "c2", "title": "Complete SOC2 security compliance review", "priority": "critical"},
            {"id": "c7", "title": "Review auth module for React migration", "priority": "medium"},
        ]},
    ],
    "overloaded": [
        {"person": "David Kim", "load": 3, "commitments": [
            {"id": "c3", "title": "Optimize database queries"},
            {"id": "c5", "title": "Update roadmap"},
            {"id": "c8", "title": "Submit Q4 section summaries"},
        ]},
    ],
    "blocking_chains": [
        {"title": "Complete API performance audit", "owner": "Priya Patel", "blocking_count": 1},
        {"title": "Submit Q4 section summaries to Sarah", "owner": "Marcus Johnson", "blocking_count": 1},
    ],
    "total_conflicts": 4,
}

MOCK_APPROVALS = [
    {
        "id": "a1",
        "action_type": "reschedule",
        "agent_name": "scheduler",
        "description": "Reschedule 'Review auth module' for Lisa Wong to resolve same-day conflict with SOC2 review",
        "target_person": "Lisa Wong",
        "confidence_score": 0.65,
        "message_content": "Hi Lisa, you have the SOC2 review and the auth module review both due the same day. I'm proposing to move the auth review to the following day. Does that work?",
    },
    {
        "id": "a2",
        "action_type": "nudge",
        "agent_name": "followup",
        "description": "Follow-up nudge for 'Update roadmap' (overdue by 2 days)",
        "target_person": "David Kim",
        "confidence_score": 0.60,
        "message_content": "Hey David, the roadmap update was due a couple of days ago. Quick pulse check \u2014 still planning to get to it, or should we flag it?",
    },
    {
        "id": "a3",
        "action_type": "escalate",
        "agent_name": "escalation",
        "description": "ESCALATION: 'Complete API performance audit' is blocking David's query optimization work",
        "target_person": "Priya Patel",
        "confidence_score": 0.55,
        "message_content": "Escalation: Priya's API performance audit is blocking David's query optimization. The audit was due yesterday. This needs attention to unblock the downstream work.",
    },
]


MOCK_DECISIONS = [
    {"title": "Adopt React for new customer dashboard", "made_by": "Sarah Chen", "description": "Team decided to use React instead of Vue for the new customer dashboard rebuild"},
    {"title": "Postpone mobile app update to Q1", "made_by": "Sarah Chen", "description": "Mobile app update deprioritized due to bandwidth constraints"},
    {"title": "SOC2 review is top priority for Lisa", "made_by": "Sarah Chen", "description": "SOC2 compliance review takes precedence over all other security work"},
]

st.set_page_config(
    page_title="Cadence - AI Chief of Staff",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Global CSS Design System ---
st.markdown("""
<style>
    /* Global smoothing */
    * { transition: all 0.15s ease; }
    
    /* Cards */
    .card {
        padding: 16px 20px; margin: 8px 0;
        border-radius: 14px; border: 1px solid rgba(128,128,128,0.1);
        background: rgba(128,128,128,0.03);
        color: inherit;
    }
    .card:hover { border-color: rgba(102,126,234,0.3); background: rgba(102,126,234,0.04); }
    .card-accent-purple { border-left: 4px solid #667eea; }
    .card-accent-red { border-left: 4px solid #ef4444; }
    .card-accent-amber { border-left: 4px solid #f59e0b; }
    .card-accent-green { border-left: 4px solid #10b981; }
    
    .card strong, .card code { color: inherit; }
    .card code { background: rgba(128,128,128,0.15); padding: 1px 6px; border-radius: 4px; font-size: 0.85em; }
    
    /* Page headers */
    .page-header {
        font-size: 1.8rem; font-weight: 800; margin: 0 0 4px;
        background: linear-gradient(135deg, #667eea, #00d4ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .page-subtitle { font-size: 0.9rem; opacity: 0.55; margin: 0 0 24px; }
    
    /* Metrics */
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .metric-card {
        padding: 16px; border-radius: 14px; text-align: center;
        background: rgba(128,128,128,0.04); border: 1px solid rgba(128,128,128,0.08);
    }
    .metric-card .value { font-size: 1.8rem; font-weight: 800; line-height: 1.1; }
    .metric-card .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.5; margin-top: 4px; }
    .mc-purple .value { color: #667eea; }
    .mc-red .value { color: #ef4444; }
    .mc-amber .value { color: #f59e0b; }
    .mc-blue .value { color: #3b82f6; }
    .mc-green .value { color: #10b981; }

    
    /* List items */
    .list-item {
        display: flex; align-items: center; gap: 12px;
        padding: 12px 16px; margin: 4px 0; border-radius: 12px;
        background: rgba(128,128,128,0.03); border: 1px solid rgba(128,128,128,0.06);
    }
    .list-item:hover { background: rgba(102,126,234,0.05); border-color: rgba(102,126,234,0.15); }
    .list-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0; }
    .list-content { flex: 1; min-width: 0; }
    .list-title { font-weight: 600; font-size: 0.88rem; margin: 0; }
    .list-meta { font-size: 0.75rem; opacity: 0.55; margin: 2px 0 0; }
    .list-right { text-align: right; flex-shrink: 0; }
    .list-score { font-size: 0.82rem; font-weight: 700; }
    .list-sub { font-size: 0.7rem; opacity: 0.45; }
    
    /* Badges */
    .badge {
        display: inline-block; padding: 2px 8px; border-radius: 6px;
        font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px;
    }
    .badge-red { background: rgba(239,68,68,0.12); color: #ef4444; }
    .badge-blue { background: rgba(59,130,246,0.12); color: #3b82f6; }
    .badge-amber { background: rgba(245,158,11,0.12); color: #f59e0b; }
    .badge-purple { background: rgba(139,92,246,0.12); color: #8b5cf6; }
    .badge-green { background: rgba(16,185,129,0.12); color: #10b981; }
    
    /* Sidebar stats */
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; font-size: 0.82rem; border-bottom: 1px solid rgba(128,128,128,0.06); }
    .stat-row:last-child { border-bottom: none; }
    .stat-val { font-weight: 700; }
    
    /* Dividers */
    .section-divider { height: 1px; background: rgba(128,128,128,0.1); margin: 20px 0; }
</style>
""", unsafe_allow_html=True)



# --- Helper Functions ---

_session = requests.Session()


def api_get(endpoint: str):
    """API GET with fallback to demo data."""
    try:
        response = _session.get(f"{API_BASE}{endpoint}", timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    # Fallback to demo data
    if DEMO_MODE:
        return _get_mock_data(endpoint)
    return None


@st.cache_data(ttl=10)
def api_get_cached(endpoint: str):
    """Cached API GET with fallback to demo data."""
    try:
        response = _session.get(f"{API_BASE}{endpoint}", timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    if DEMO_MODE:
        return _get_mock_data(endpoint)
    return None


def api_post(endpoint: str, data: dict = None):
    """API POST with demo mode simulation."""
    try:
        response = _session.post(f"{API_BASE}{endpoint}", json=data, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    if DEMO_MODE:
        return _simulate_post(endpoint, data)
    return None



def _get_mock_data(endpoint: str):
    """Return mock data for demo mode."""
    if endpoint == "/stats":
        return MOCK_STATS
    elif endpoint == "/dashboard":
        return MOCK_DASHBOARD
    elif endpoint == "/commitments":
        return MOCK_COMMITMENTS
    elif endpoint == "/conflicts":
        return MOCK_CONFLICTS
    elif endpoint == "/approvals":
        return MOCK_APPROVALS
    elif endpoint == "/decisions":
        return MOCK_DECISIONS
    elif endpoint == "/graph/export":
        return {"nodes": [
            {"_label": "Person", "id": "p1", "name": "Sarah Chen"},
            {"_label": "Person", "id": "p2", "name": "Marcus Johnson"},
            {"_label": "Person", "id": "p3", "name": "Priya Patel"},
            {"_label": "Person", "id": "p4", "name": "David Kim"},
            {"_label": "Person", "id": "p5", "name": "Lisa Wong"},
            {"_label": "Commitment", "id": "c1", "title": "API performance audit"},
            {"_label": "Commitment", "id": "c2", "title": "SOC2 review"},
            {"_label": "Commitment", "id": "c3", "title": "DB query optimization"},
            {"_label": "Commitment", "id": "c4", "title": "React migration plan"},
            {"_label": "Decision", "id": "d1", "title": "Adopt React"},
            {"_label": "Decision", "id": "d2", "title": "Postpone mobile app"},
        ], "edges": [
            {"source": "p3", "target": "c1", "relationship": "OWNS"},
            {"source": "p5", "target": "c2", "relationship": "OWNS"},
            {"source": "p4", "target": "c3", "relationship": "OWNS"},
            {"source": "p2", "target": "c4", "relationship": "OWNS"},
            {"source": "c3", "target": "c1", "relationship": "DEPENDS_ON"},
            {"source": "p1", "target": "d1", "relationship": "MADE_DECISION"},
            {"source": "p1", "target": "d2", "relationship": "MADE_DECISION"},
        ]}
    return None



def _simulate_post(endpoint: str, data: dict = None):
    """Simulate POST responses in demo mode with REAL text parsing."""
    if endpoint == "/ingest" and data:
        # Actually parse the transcript text
        text = data.get("text", "")
        participants = data.get("participants", [])
        commitments, decisions = _extract_from_text(text, participants)
        return {
            "commitments": commitments,
            "decisions": decisions,
            "source_type": data.get("source_type", "meeting_transcript"),
            "processed_at": datetime.now().isoformat(),
        }
    elif "/agents" in endpoint:
        return {"message": "Agent run complete (demo mode)", "results": {"scheduler": [{"description": "Proposed reschedule for Lisa Wong"}], "followup": [{"description": "Nudge sent to David Kim"}], "escalation": []}}
    elif "/approvals/review" in endpoint:
        return {"message": "Action approved (demo mode)", "action_id": data.get("action_id", ""), "status": "approved", "executed_at": datetime.now().isoformat()}
    return {"message": "OK (demo mode)"}


def _extract_from_text(text: str, participants: list) -> tuple:
    """
    Real-time heuristic extraction from transcript text.
    Handles both formatted (line-per-speaker) and run-on transcripts.
    """
    import re

    # Step 1: Normalize — split run-on text into speaker segments
    # Look for patterns like "Name:" or "Name (Role):" in the text
    # Build a regex from known participants
    known_names = [p.strip() for p in participants if p.strip()]

    # Build speaker split pattern from participants
    if known_names:
        # Escape names for regex and create pattern like "Alex:|Priya:|Marcus:"
        name_patterns = [re.escape(name) for name in known_names]
        # Also match "Name (Role):" format
        speaker_pattern = r'(?=' + '|'.join(
            [f'(?:{np}(?:\\s*\\([^)]*\\))?\\s*:)' for np in name_patterns]
        ) + ')'
        # Split text at speaker boundaries
        segments = re.split(speaker_pattern, text)
        segments = [s.strip() for s in segments if s.strip()]
    else:
        # No participants provided — try generic "CapitalizedWord:" pattern
        segments = re.split(r'(?=[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s*\([^)]*\))?\s*:)', text)
        segments = [s.strip() for s in segments if s.strip()]

    # If splitting didn't help, fall back to sentence splitting
    if len(segments) <= 1:
        # Split on periods, but keep the speaker prefix
        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        segments = [s.strip() for s in raw_sentences if len(s.strip()) > 15]

    commitments = []
    decisions = []
    seen_commitments = set()
    seen_decisions = set()

    # Action/commitment keywords
    action_keywords = [
        "will", "going to", "need to", "needs to", "should", "must",
        "handle", "own", "responsible for", "take care of",
        "deliver", "complete", "finish", "prepare", "submit",
        "by end of", "by friday", "by monday", "by thursday", "by next week",
        "deadline", "due", "target date", "committed to",
        "action item", "follow up", "i'll", "i will", "we will",
        "let me", "i can", "i'll take", "let's aim", "aim to",
        "merge", "deploy", "ship", "launch", "release",
        "add", "implement", "build", "create", "fix", "update",
        "run", "schedule", "plan to",
    ]

    # Decision keywords
    decision_keywords = [
        "decided", "agreed", "we'll go with", "let's go with",
        "final decision", "we chose", "approved", "selected",
        "moving forward with", "the plan is", "we're going with",
        "consensus", "confirmed", "settled on", "let's do",
    ]

    # Priority keywords
    high_priority_kw = ["asap", "urgent", "critical", "blocker", "top priority", "immediately", "crucial", "before next week", "client demo"]
    low_priority_kw = ["nice to have", "eventually", "low priority", "when possible", "if time allows"]

    # Deadline regex
    deadline_pattern = re.compile(
        r'by\s+(end\s+of\s+)?(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
        r'week|month|quarter|eod|end\s+of\s+day|tomorrow|'
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}|'
        r'\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2})',
        re.IGNORECASE
    )

    # Also match "before X" pattern
    before_pattern = re.compile(
        r'before\s+(next\s+)?(monday|tuesday|wednesday|thursday|friday|week|'
        r'the\s+\w+\s+demo|the\s+\w+\s+meeting|launch|release)',
        re.IGNORECASE
    )

    for segment in segments:
        if not segment or len(segment) < 12:
            continue

        segment_lower = segment.lower()

        # Extract the speaker from this segment (if "Name: content" format)
        speaker = "Unassigned"
        content = segment

        colon_match = re.match(r'^([A-Z][a-zA-Z\s]*?)(?:\s*\([^)]*\))?\s*:\s*(.+)', segment)
        if colon_match:
            potential_speaker = colon_match.group(1).strip()
            # Verify it's a reasonable name (1-3 words, capitalized)
            if len(potential_speaker.split()) <= 3 and potential_speaker[0].isupper():
                speaker = potential_speaker
                content = colon_match.group(2).strip()

        content_lower = content.lower()

        # Further split content into sentences if it contains multiple
        sentences = re.split(r'(?<=[.!?])\s+', content)

        for sentence in sentences:
            if not sentence or len(sentence) < 12:
                continue
            sent_lower = sentence.lower()

            # Check for commitments
            is_commitment = any(kw in sent_lower for kw in action_keywords)

            if is_commitment:
                # Determine priority
                priority = "medium"
                if any(kw in sent_lower for kw in high_priority_kw):
                    priority = "high"
                elif any(kw in sent_lower for kw in low_priority_kw):
                    priority = "low"

                # Extract deadline
                deadline = None
                dl_match = deadline_pattern.search(sentence)
                if dl_match:
                    deadline = dl_match.group(0)
                else:
                    bf_match = before_pattern.search(sentence)
                    if bf_match:
                        deadline = bf_match.group(0)

                # Title: use the sentence, cleaned up
                title = sentence.strip()
                if len(title) > 80:
                    title = title[:77] + "..."

                # Dedup
                title_key = title.lower()[:35]
                if title_key not in seen_commitments:
                    seen_commitments.add(title_key)
                    commitments.append({
                        "title": title,
                        "owner_name": speaker,
                        "priority": priority,
                        "deadline": deadline or "TBD",
                        "description": sentence.strip(),
                    })

            # Check for decisions
            is_decision = any(kw in sent_lower for kw in decision_keywords)
            if is_decision:
                title = sentence.strip()
                if len(title) > 80:
                    title = title[:77] + "..."

                title_key = title.lower()[:35]
                if title_key not in seen_decisions:
                    seen_decisions.add(title_key)
                    decisions.append({
                        "title": title,
                        "made_by": speaker,
                        "description": sentence.strip(),
                    })

    # If nothing found with strict matching, do a lenient pass
    if not commitments and not decisions:
        for segment in segments:
            if len(segment) < 15:
                continue
            # Extract speaker
            speaker = "Unassigned"
            content = segment
            colon_match = re.match(r'^([A-Z][a-zA-Z\s]*?)(?:\s*\([^)]*\))?\s*:\s*(.+)', segment)
            if colon_match:
                speaker = colon_match.group(1).strip()
                content = colon_match.group(2).strip()

            if any(w in content.lower() for w in ["report", "discuss", "present", "review", "update", "share", "provide", "work on"]):
                title = content[:80] if len(content) > 80 else content
                commitments.append({
                    "title": title,
                    "owner_name": speaker,
                    "priority": "medium",
                    "deadline": "TBD",
                    "description": content,
                })
                if len(commitments) >= 5:
                    break

    return commitments, decisions


def get_priority_color(priority: str) -> str:
    """Get color for priority level."""
    colors = {
        "critical": "#e74c3c",
        "high": "#e67e22",
        "medium": "#3498db",
        "low": "#95a5a6",
    }
    return colors.get(priority, "#95a5a6")


def get_status_emoji(status: str) -> str:
    """Get emoji for status."""
    emojis = {
        "pending": "\U0001f7e1",
        "accepted": "\U0001f535",
        "in_progress": "\U0001f504",
        "completed": "\u2705",
        "overdue": "\U0001f534",
        "escalated": "\U0001f6a8",
    }
    return emojis.get(status, "\u26aa")



# --- Sidebar ---

with st.sidebar:
    # Logo
    st.markdown("""
    <div style="text-align: center; padding: 16px 0 8px;">
        <div style="
            width: 56px; height: 56px; margin: 0 auto 8px;
            background: #0f0f23; border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            position: relative; box-shadow: 0 4px 12px rgba(102,126,234,0.3);
        ">
            <span style="
                font-size: 32px; font-weight: 900; font-style: italic;
                background: linear-gradient(135deg, #a855f7, #667eea, #00d4ff);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                line-height: 1;
            ">C</span>
            <span style="
                position: absolute; top: 6px; right: 8px;
                font-size: 14px; color: #00d4ff;
                text-shadow: 0 0 6px #00d4ff;
            ">&#10022;</span>
        </div>
        <h2 style="margin: 0; font-size: 1.3rem; font-weight: 800; background: linear-gradient(135deg, #667eea, #00d4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Cadence</h2>
        <p style="opacity: 0.5; font-size: 0.75rem; margin: 2px 0 0;">AI Chief of Staff</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True)

    # Custom CSS to hide Streamlit's default radio styling and create hover-enlarge nav
    st.markdown("""
    <style>
        /* Hide default radio button styling in sidebar */
        section[data-testid="stSidebar"] .stRadio > div {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        section[data-testid="stSidebar"] .stRadio > div > label {
            display: flex !important;
            align-items: center;
            padding: 10px 14px !important;
            border-radius: 12px !important;
            cursor: pointer !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            border: 1px solid transparent !important;
            margin: 0 !important;
            background: transparent !important;
        }
        /* Hover: enlarge and highlight */
        section[data-testid="stSidebar"] .stRadio > div > label:hover {
            transform: scale(1.04) translateX(4px) !important;
            background: rgba(102, 126, 234, 0.08) !important;
            border-color: rgba(102, 126, 234, 0.2) !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            padding: 12px 16px !important;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1) !important;
        }
        /* Selected/active state */
        section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"],
        section[data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
            background: rgba(102, 126, 234, 0.12) !important;
            border-color: rgba(102, 126, 234, 0.3) !important;
            font-weight: 700 !important;
            transform: scale(1.02) !important;
            box-shadow: 0 2px 12px rgba(102, 126, 234, 0.15) !important;
        }
        /* Hide the radio circle */
        section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
            display: none !important;
        }
        /* Style the radio label text */
        section[data-testid="stSidebar"] .stRadio > div > label > div:last-child p {
            margin: 0 !important;
            font-size: inherit !important;
        }

        /* Stats section styling */
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 8px;
        }
        .stat-card {
            padding: 12px;
            border-radius: 12px;
            text-align: center;
            background: rgba(128, 128, 128, 0.06);
            border: 1px solid rgba(128, 128, 128, 0.08);
            transition: all 0.2s ease;
        }
        .stat-card:hover {
            background: rgba(102, 126, 234, 0.06);
            border-color: rgba(102, 126, 234, 0.15);
            transform: scale(1.02);
        }
        .stat-card .stat-number {
            font-size: 1.5rem;
            font-weight: 800;
            line-height: 1.2;
            background: linear-gradient(135deg, #667eea, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .stat-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.6;
            margin-top: 2px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Navigation (using radio but styled as modern pills)
    page = st.radio(
        "",
        [
            "\U0001f4ca Dashboard",
            "\U0001f4dd Ingest",
            "\U0001f50d Commitments",
            "\u26a0\ufe0f Conflicts",
            "\u2705 Approvals",
            "\U0001f916 Agents",
            "\U0001f578\ufe0f Graph",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.divider()

    # Stats section - larger, more readable with 2x2 grid
    stats = api_get("/stats")
    if stats:
        commitments = stats.get("commitments", 0)
        people = stats.get("people", 0)
        decisions = stats.get("decisions", 0)
        pending = stats.get("pending_approvals", 0)

        st.markdown(f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{commitments}</div>
                <div class="stat-label">Commitments</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{people}</div>
                <div class="stat-label">People</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{decisions}</div>
                <div class="stat-label">Decisions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{pending}</div>
                <div class="stat-label">Approvals</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if DEMO_MODE:
            st.markdown('<p style="text-align:center; font-size: 0.85rem; opacity: 0.6; margin-top: 12px;">&#127919; Demo Mode Active</p>', unsafe_allow_html=True)
        else:
            st.info("API not connected.")



# =============================================================================
# PAGE: Dashboard
# =============================================================================

if page == "\U0001f4ca Dashboard":
    st.markdown('<h1 class="page-header">Decision Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">What needs your attention today — ranked by urgency, impact, and blocking count</p>', unsafe_allow_html=True)

    dashboard = api_get("/dashboard")
    if dashboard:
        items = dashboard.get("items", [])
        summary = dashboard.get("summary", {})

        total_items = summary.get("total_items", 0)
        high_urgency = summary.get("high_urgency", 0)
        blocking_items = summary.get("blocking_items", 0)
        pending_approvals = dashboard.get("pending_approvals", 0)

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card mc-purple">
                <div class="value">{total_items}</div>
                <div class="label">Action Items</div>
            </div>
            <div class="metric-card mc-red">
                <div class="value">{high_urgency}</div>
                <div class="label">High Urgency</div>
            </div>
            <div class="metric-card mc-amber">
                <div class="value">{blocking_items}</div>
                <div class="label">Blocking Others</div>
            </div>
            <div class="metric-card mc-blue">
                <div class="value">{pending_approvals}</div>
                <div class="label">Pending Approvals</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


        # Items list
        if items:
            st.markdown("#### \U0001f3af Priority Items")
            st.caption("Ranked by urgency \u00d7 impact \u00d7 downstream blocking")

            for item in items[:10]:
                urgency = item.get("urgency_score", 0)
                blocking = item.get("blocking_count", 0)
                title = item.get("title", "Untitled")
                owner = item.get("owner", "Unknown")
                status = item.get("status", "pending")
                deadline = item.get("deadline", "")

                # Urgency indicator
                if urgency >= 0.8:
                    urgency_icon = "\U0001f534"
                    icon_bg = "rgba(239,68,68,0.12)"
                elif urgency >= 0.5:
                    urgency_icon = "\U0001f7e0"
                    icon_bg = "rgba(245,158,11,0.12)"
                else:
                    urgency_icon = "\U0001f7e2"
                    icon_bg = "rgba(34,197,94,0.12)"

                # Status badge class
                badge_map = {"overdue": "badge-red", "in_progress": "badge-blue", "pending": "badge-amber", "escalated": "badge-purple", "completed": "badge-green"}
                badge_class = badge_map.get(status, "badge-amber")

                # Meta info
                meta_parts = [f"Owner: {owner}"]
                if blocking > 0:
                    meta_parts.append(f"\u26d3\ufe0f Blocking {blocking}")

                deadline_str = str(deadline)[:10] if deadline else ""
                status_display = status.replace("_", " ")
                meta_str = " \u00b7 ".join(meta_parts)

                st.markdown(f"""
                <div class="list-item">
                    <div class="list-icon" style="background: {icon_bg};">{urgency_icon}</div>
                    <div class="list-content">
                        <p class="list-title">{title}</p>
                        <p class="list-meta">{meta_str}</p>
                    </div>
                    <div class="list-right">
                        <div class="list-score">{urgency:.0%}</div>
                        <div class="list-sub">{deadline_str}</div>
                        <span class="badge {badge_class}">{status_display}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        else:
            st.success("\u2728 All clear! No items need your attention right now.")
    else:
        st.info("Loading dashboard data...")



# =============================================================================
# PAGE: Ingest
# =============================================================================

elif page == "\U0001f4dd Ingest":
    st.markdown('<h1 class="page-header">Ingest Communication</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Upload a meeting transcript, Slack thread, or calendar invite to extract commitments</p>', unsafe_allow_html=True)

    source_type = st.selectbox(
        "Source Type",
        ["meeting_transcript", "slack_thread", "calendar_invite"],
        format_func=lambda x: {
            "meeting_transcript": "\U0001f4cb Meeting Transcript",
            "slack_thread": "\U0001f4ac Slack Thread",
            "calendar_invite": "\U0001f4c5 Calendar Invite",
        }[x],
    )

    meeting_title = st.text_input("Meeting/Thread Title", placeholder="Q4 Planning Sync")
    participants = st.text_input(
        "Participants (comma-separated)",
        placeholder="Alice, Bob, Charlie",
    )

    text = st.text_area(
        "Paste your transcript or thread content here",
        height=300,
        placeholder=(
            "Alice: Let's finalize the Q4 roadmap by Friday.\n"
            "Bob: I'll handle the frontend migration. Should be done by next Wednesday.\n"
            "Charlie: I'll review the API specs. Need Bob's PR first though.\n"
            "Alice: Decided \u2014 we're going with React for the new dashboard.\n"
        ),
    )


    if st.button("\U0001f680 Extract Commitments", type="primary"):
        if not text.strip():
            st.error("Please paste some text to analyze.")
        else:
            with st.spinner("Extracting commitments and decisions..."):
                payload = {
                    "text": text,
                    "source_type": source_type,
                    "meeting_title": meeting_title or None,
                    "participants": [p.strip() for p in participants.split(",") if p.strip()],
                }
                result = api_post("/ingest", payload)

            if result:
                commitments = result.get("commitments", [])
                decisions = result.get("decisions", [])

                st.success(
                    f"Extracted **{len(commitments)} commitments** and "
                    f"**{len(decisions)} decisions**!"
                )

                if commitments:
                    st.subheader("\U0001f4cc Commitments Found")
                    for c in commitments:
                        priority_color = get_priority_color(c.get("priority", "medium"))
                        st.markdown(
                            f'<div class="card card-accent-purple">'
                            f'<strong>{c.get("title", "Untitled")}</strong><br>'
                            f'Owner: <code>{c.get("owner_name", "Unknown")}</code> | '
                            f'Priority: <span style="color:{priority_color}">'
                            f'{c.get("priority", "medium").upper()}</span> | '
                            f'Deadline: {c.get("deadline", "TBD")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if decisions:
                    st.subheader("\U0001f3af Decisions Identified")
                    for d in decisions:
                        st.markdown(
                            f'<div class="card card-accent-purple">'
                            f'<strong>{d.get("title", "Untitled")}</strong><br>'
                            f'Made by: <code>{d.get("made_by", "Unknown")}</code>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
            else:
                st.error("Extraction failed. Check that the backend is running.")



# =============================================================================
# PAGE: Commitments
# =============================================================================

elif page == "\U0001f50d Commitments":
    st.markdown('<h1 class="page-header">All Commitments</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">View and manage all tracked commitments across your team</p>', unsafe_allow_html=True)

    commitments = api_get("/commitments")
    if commitments:
        # Filter controls
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                ["pending", "accepted", "in_progress", "completed", "overdue", "escalated"],
                default=["pending", "in_progress", "overdue", "escalated"],
            )
        with col2:
            search = st.text_input("Search", placeholder="Search commitments...")

        filtered = commitments
        if status_filter:
            filtered = [c for c in filtered if c.get("status") in status_filter]
        if search:
            filtered = [
                c for c in filtered
                if search.lower() in str(c.get("title", "")).lower()
                or search.lower() in str(c.get("owner_name", "")).lower()
            ]

        st.markdown(f"**Showing {len(filtered)} of {len(commitments)} commitments**")

        for c in filtered:
            status = c.get("status", "pending")
            emoji = get_status_emoji(status)
            priority = c.get("priority", "medium")
            priority_color = get_priority_color(priority)

            with st.expander(f"{emoji} {c.get('title', 'Untitled')} \u2014 {c.get('owner_name', c.get('owner', 'Unknown'))}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Status:** {emoji} `{status}`")
                with col2:
                    st.markdown(
                        f'**Priority:** <span style="color:{priority_color}">'
                        f'{priority.upper()}</span>',
                        unsafe_allow_html=True,
                    )
                with col3:
                    st.markdown(f"**Deadline:** {c.get('deadline', 'None')}")

                if c.get("description"):
                    st.markdown(f"*{c['description']}*")

                st.caption(
                    f"ID: {c.get('id', 'N/A')} | Created: {c.get('created_at', 'N/A')}"
                )
    else:
        st.info("No commitments found. Ingest a transcript to get started!")



# =============================================================================
# PAGE: Conflicts
# =============================================================================

elif page == "\u26a0\ufe0f Conflicts":
    st.markdown('<h1 class="page-header">Conflicts</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Schedule conflicts, overloaded members, blocking chains</p>', unsafe_allow_html=True)

    conflicts = api_get("/conflicts")
    if conflicts:
        total = conflicts.get("total_conflicts", 0)

        if total == 0:
            st.success("No conflicts detected! Your team is well-balanced.")
        else:
            st.error(f"**{total} conflicts detected** \u2014 review below")

            # Schedule Conflicts
            schedule = conflicts.get("schedule_conflicts", [])
            if schedule:
                st.subheader("\U0001f4c5 Schedule Conflicts")
                st.caption("Same person, multiple commitments due the same day")
                for s in schedule:
                    st.markdown(
                        f'<div class="card card-accent-red">'
                        f'<strong>{s.get("person", "Unknown")}</strong> has '
                        f'{len(s.get("conflicts", []))} items due on '
                        f'<code>{s.get("due_date", "?")}</code>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    for item in s.get("conflicts", []):
                        st.markdown(f"  - {item.get('title', 'Unknown')}")

            # Overloaded
            overloaded = conflicts.get("overloaded", [])
            if overloaded:
                st.subheader("\U0001f3cb\ufe0f Overloaded Team Members")
                st.caption("People with 3+ active commitments")
                for o in overloaded:
                    st.markdown(
                        f'<div class="card card-accent-red">'
                        f'<strong>{o.get("person", "Unknown")}</strong> \u2014 '
                        f'{o.get("load", 0)} active commitments'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Blocking Chains
            blocking = conflicts.get("blocking_chains", [])
            if blocking:
                st.subheader("\U0001f517 Blocking Chains")
                st.caption("Items blocking multiple downstream tasks")
                for b in blocking:
                    st.markdown(
                        f'<div class="card card-accent-red">'
                        f'<strong>{b.get("title", "Unknown")}</strong> '
                        f'(owned by {b.get("owner", "Unknown")}) is blocking '
                        f'<strong>{b.get("blocking_count", 0)}</strong> items'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("Connect to the API to detect conflicts.")



# =============================================================================
# PAGE: Approvals
# =============================================================================

elif page == "\u2705 Approvals":
    st.markdown('<h1 class="page-header">Approval Gate</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Review and approve agent-proposed actions. Trust is the product, not a feature.</p>', unsafe_allow_html=True)

    # Initialize session state for approval tracking
    if "approved_ids" not in st.session_state:
        st.session_state.approved_ids = set()
    if "rejected_actions" not in st.session_state:
        st.session_state.rejected_actions = []

    approvals = api_get("/approvals")
    if approvals:
        # Filter out approved and rejected items
        pending = [a for a in approvals if a.get("id") not in st.session_state.approved_ids and a.get("id") not in [r.get("id") for r in st.session_state.rejected_actions]]

        if not pending and not st.session_state.rejected_actions:
            st.success("All clear! No actions awaiting approval. Agents are operating within auto-approve thresholds.")
        else:
            # --- PENDING SECTION ---
            if pending:
                st.warning(f"**{len(pending)} actions awaiting your review**")

                for action in pending:
                    action_type = action.get("action_type", "unknown")
                    type_emoji = {"nudge": "\U0001f4ac", "reschedule": "\U0001f4c5", "escalate": "\U0001f6a8", "task_sync": "\U0001f504"}.get(action_type, "\u26a1")

                    with st.container():
                        st.markdown(
                            f'<div class="card card-accent-amber">'
                            f'<strong>{type_emoji} {action.get("description", "No description")}</strong><br>'
                            f'Agent: <code>{action.get("agent_name", "unknown")}</code> | '
                            f'Confidence: <strong>{action.get("confidence_score", 0):.0%}</strong> | '
                            f'Target: <code>{action.get("target_person", "Unknown")}</code>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        if action.get("message_content"):
                            with st.expander("Preview message"):
                                st.info(action["message_content"])

                        col1, col2, col3 = st.columns([1, 1, 4])
                        with col1:
                            if st.button("\u2705 Approve", key=f"approve_{action.get('id')}"):
                                st.session_state.approved_ids.add(action["id"])
                                api_post("/approvals/review", {"action_id": action["id"], "approved": True})
                                st.rerun()
                        with col2:
                            if st.button("\u274c Reject", key=f"reject_{action.get('id')}"):
                                st.session_state.rejected_actions.append(action)
                                api_post("/approvals/review", {"action_id": action["id"], "approved": False})
                                st.rerun()

                        st.divider()

            elif not st.session_state.rejected_actions:
                st.success("\u2728 All pending actions have been reviewed!")

            # --- UNDER REVIEW SECTION (rejected items) ---
            if st.session_state.rejected_actions:
                st.markdown('<div style="height: 24px;"></div>', unsafe_allow_html=True)
                st.markdown("#### \U0001f504 Under Review")
                st.caption("Previously rejected actions \u2014 you can reconsider and approve them")

                for idx, action in enumerate(st.session_state.rejected_actions):
                    action_type = action.get("action_type", "unknown")
                    type_emoji = {"nudge": "\U0001f4ac", "reschedule": "\U0001f4c5", "escalate": "\U0001f6a8", "task_sync": "\U0001f504"}.get(action_type, "\u26a1")

                    with st.container():
                        st.markdown(
                            f'<div class="card" style="border-left: 4px solid rgba(128,128,128,0.3); opacity: 0.85;">'
                            f'<strong>{type_emoji} {action.get("description", "No description")}</strong><br>'
                            f'Agent: <code>{action.get("agent_name", "unknown")}</code> | '
                            f'Confidence: <strong>{action.get("confidence_score", 0):.0%}</strong> | '
                            f'Target: <code>{action.get("target_person", "Unknown")}</code><br>'
                            f'<span class="badge badge-red" style="margin-top: 6px;">REJECTED</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        if action.get("message_content"):
                            with st.expander("Preview message", expanded=False):
                                st.info(action["message_content"])

                        col1, col2, col3 = st.columns([1.2, 1.2, 3.6])
                        with col1:
                            if st.button("\u2705 Approve Instead", key=f"reapprove_{action.get('id')}_{idx}"):
                                st.session_state.approved_ids.add(action["id"])
                                st.session_state.rejected_actions = [a for a in st.session_state.rejected_actions if a.get("id") != action.get("id")]
                                api_post("/approvals/review", {"action_id": action["id"], "approved": True})
                                st.rerun()
                        with col2:
                            if st.button("\U0001f5d1 Dismiss", key=f"dismiss_{action.get('id')}_{idx}"):
                                st.session_state.approved_ids.add(action["id"])  # Just remove it
                                st.session_state.rejected_actions = [a for a in st.session_state.rejected_actions if a.get("id") != action.get("id")]
                                st.rerun()

                        st.divider()

    else:
        st.info("No pending approvals or API not connected.")



# =============================================================================
# PAGE: Agents
# =============================================================================

elif page == "\U0001f916 Agents":
    st.markdown('<h1 class="page-header">Orchestration Agents</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Manually trigger the scheduler, follow-up, and escalation agents</p>', unsafe_allow_html=True)

    st.markdown("""
    | Agent | Decision Style | Purpose |
    |-------|---------------|---------|
    | **Scheduler** | Deterministic | Detect conflicts, propose reschedules |
    | **Follow-up** | Generative | Nudge owners of stale/overdue items |
    | **Escalation** | Deterministic | Escalate critically blocked/overdue items |
    """)

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("\U0001f680 Run All Agents", type="primary"):
            with st.spinner("Running all agents..."):
                result = api_post("/agents/run")
            if result:
                results = result.get("results", {})
                total = sum(len(v) for v in results.values())
                st.success(f"Complete! {total} actions proposed")
                for agent, actions in results.items():
                    st.markdown(f"**{agent.title()}**: {len(actions)} actions")
            else:
                st.error("Agent run failed. Check backend logs.")

    with col2:
        if st.button("\U0001f4c5 Scheduler"):
            with st.spinner("Running scheduler..."):
                result = api_post("/agents/scheduler")
            if result:
                st.success(f"Scheduler: {result.get('actions_proposed', 0)} actions")

    with col3:
        if st.button("\U0001f4ac Follow-up"):
            with st.spinner("Running follow-up..."):
                result = api_post("/agents/followup")
            if result:
                st.success(f"Follow-up: {result.get('actions_proposed', 0)} actions")

    with col4:
        if st.button("\U0001f6a8 Escalation"):
            with st.spinner("Running escalation..."):
                result = api_post("/agents/escalation")
            if result:
                st.success(f"Escalation: {result.get('actions_proposed', 0)} actions")



# =============================================================================
# PAGE: Knowledge Graph
# =============================================================================

elif page == "\U0001f578\ufe0f Graph":
    st.markdown('<h1 class="page-header">Knowledge Graph</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Explore the cross-tool knowledge graph linking people, decisions, and tasks</p>', unsafe_allow_html=True)

    graph_data = api_get("/graph/export")
    if graph_data:
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nodes", len(nodes))
        with col2:
            st.metric("Relationships", len(edges))
        with col3:
            st.metric("Node Types", len(set(n.get("_label", "") for n in nodes)))

        if nodes:
            # Build D3.js interactive visualization
            import json as _json

            # Enrich nodes with additional display info
            d3_nodes = []
            for node in nodes:
                label = node.get("_label", "Unknown")
                name = node.get("name") or node.get("title") or node.get("id", "?")
                d3_nodes.append({
                    "id": node.get("id", name),
                    "label": str(name),
                    "type": label,
                    "details": {k: v for k, v in node.items() if k != "_label" and v is not None},
                })

            d3_edges = []
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                if source and target:
                    d3_edges.append({
                        "source": source,
                        "target": target,
                        "relationship": edge.get("relationship", ""),
                    })

            graph_json = _json.dumps({"nodes": d3_nodes, "links": d3_edges})


            # D3.js Force-Directed Graph with click-to-expand details
            d3_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://d3js.org/d3.v7.min.js"></script>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fafbfc; }}
                    #graph-container {{ width: 100%; height: 520px; position: relative; border: 1px solid #e1e5e9; border-radius: 12px; overflow: hidden; background: #ffffff; }}
                    svg {{ width: 100%; height: 100%; }}
                    
                    .node {{ cursor: pointer; transition: transform 0.2s; }}
                    .node:hover circle {{ stroke-width: 3px; stroke: #1a1a2e; }}
                    .node text {{ font-size: 11px; fill: #333; pointer-events: none; font-weight: 500; }}
                    
                    .link {{ stroke: #cbd5e1; stroke-opacity: 0.6; stroke-width: 1.5px; }}
                    .link-label {{ font-size: 9px; fill: #94a3b8; pointer-events: none; }}
                    
                    .link.highlighted {{ stroke: #667eea; stroke-opacity: 1; stroke-width: 2.5px; }}
                    .node.dimmed circle {{ opacity: 0.3; }}
                    .node.dimmed text {{ opacity: 0.3; }}
                    .link.dimmed {{ stroke-opacity: 0.1; }}

                    
                    #detail-panel {{
                        position: absolute; top: 12px; right: 12px;
                        width: 280px; background: white; border-radius: 10px;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.12); padding: 16px;
                        display: none; z-index: 100; border: 1px solid #e2e8f0;
                        max-height: 480px; overflow-y: auto;
                    }}
                    #detail-panel.visible {{ display: block; animation: slideIn 0.2s ease; }}
                    @keyframes slideIn {{ from {{ opacity: 0; transform: translateX(10px); }} to {{ opacity: 1; transform: translateX(0); }} }}
                    
                    #detail-panel h3 {{ font-size: 14px; color: #1a1a2e; margin-bottom: 8px; }}
                    #detail-panel .type-badge {{
                        display: inline-block; padding: 2px 8px; border-radius: 10px;
                        font-size: 11px; font-weight: 600; margin-bottom: 10px;
                    }}
                    #detail-panel .detail-row {{ font-size: 12px; color: #475569; margin: 6px 0; line-height: 1.5; }}
                    #detail-panel .detail-row strong {{ color: #1e293b; }}
                    #detail-panel .close-btn {{
                        position: absolute; top: 8px; right: 12px;
                        cursor: pointer; font-size: 18px; color: #94a3b8;
                        border: none; background: none;
                    }}
                    #detail-panel .close-btn:hover {{ color: #1a1a2e; }}
                    #detail-panel .connections {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; }}
                    #detail-panel .conn-item {{ font-size: 11px; color: #64748b; padding: 3px 0; }}
                    
                    #legend {{
                        position: absolute; bottom: 12px; left: 12px;
                        background: rgba(255,255,255,0.95); border-radius: 8px;
                        padding: 10px 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                        border: 1px solid #e2e8f0;
                    }}
                    #legend .legend-item {{ display: flex; align-items: center; margin: 4px 0; font-size: 11px; color: #475569; }}
                    #legend .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }}
                    
                    .tooltip {{
                        position: absolute; background: #1e293b; color: white;
                        padding: 6px 10px; border-radius: 6px; font-size: 11px;
                        pointer-events: none; opacity: 0; transition: opacity 0.15s;
                        white-space: nowrap;
                    }}
                </style>
            </head>
            <body>
                <div id="graph-container">
                    <svg></svg>
                    <div id="detail-panel">
                        <button class="close-btn" onclick="closePanel()">\u00d7</button>
                        <div id="panel-content"></div>
                    </div>
                    <div id="legend">
                        <div class="legend-item"><div class="legend-dot" style="background:#667eea"></div>People</div>
                        <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>Commitments</div>
                        <div class="legend-item"><div class="legend-dot" style="background:#10b981"></div>Decisions</div>
                    </div>
                    <div class="tooltip" id="tooltip"></div>
                </div>


                <script>
                    const data = {graph_json};
                    
                    const colorMap = {{
                        "Person": "#667eea",
                        "Commitment": "#f59e0b",
                        "Decision": "#10b981",
                        "AgentAction": "#ef4444",
                        "Conflict": "#8b5cf6",
                    }};
                    
                    const sizeMap = {{
                        "Person": 22,
                        "Commitment": 16,
                        "Decision": 14,
                        "AgentAction": 12,
                    }};

                    const container = document.getElementById("graph-container");
                    const width = container.clientWidth;
                    const height = container.clientHeight;
                    
                    const svg = d3.select("svg")
                        .attr("viewBox", [0, 0, width, height]);
                    
                    // Zoom behavior
                    const g = svg.append("g");
                    svg.call(d3.zoom()
                        .scaleExtent([0.3, 3])
                        .on("zoom", (event) => g.attr("transform", event.transform))
                    );

                    // Force simulation with good spacing
                    const simulation = d3.forceSimulation(data.nodes)
                        .force("link", d3.forceLink(data.links).id(d => d.id).distance(120))
                        .force("charge", d3.forceManyBody().strength(-400))
                        .force("center", d3.forceCenter(width / 2, height / 2))
                        .force("collision", d3.forceCollide().radius(50))
                        .force("x", d3.forceX(width / 2).strength(0.05))
                        .force("y", d3.forceY(height / 2).strength(0.05));

                    // Draw links
                    const link = g.append("g")
                        .selectAll("line")
                        .data(data.links)
                        .join("line")
                        .attr("class", "link");

                    // Link labels
                    const linkLabel = g.append("g")
                        .selectAll("text")
                        .data(data.links)
                        .join("text")
                        .attr("class", "link-label")
                        .attr("text-anchor", "middle")
                        .text(d => d.relationship);

                    // Draw nodes
                    const node = g.append("g")
                        .selectAll("g")
                        .data(data.nodes)
                        .join("g")
                        .attr("class", "node")
                        .call(d3.drag()
                            .on("start", dragstarted)
                            .on("drag", dragged)
                            .on("end", dragended));

                    node.append("circle")
                        .attr("r", d => sizeMap[d.type] || 14)
                        .attr("fill", d => colorMap[d.type] || "#94a3b8")
                        .attr("stroke", "#fff")
                        .attr("stroke-width", 2);

                    node.append("text")
                        .attr("dy", d => (sizeMap[d.type] || 14) + 14)
                        .attr("text-anchor", "middle")
                        .text(d => d.label.length > 20 ? d.label.substring(0, 18) + "..." : d.label);


                    // Hover tooltip
                    const tooltip = document.getElementById("tooltip");
                    node.on("mouseover", (event, d) => {{
                        tooltip.style.opacity = 1;
                        tooltip.innerHTML = `<strong>${{d.label}}</strong><br/>Type: ${{d.type}}`;
                        tooltip.style.left = (event.offsetX + 15) + "px";
                        tooltip.style.top = (event.offsetY - 10) + "px";
                    }})
                    .on("mouseout", () => {{ tooltip.style.opacity = 0; }});

                    // Click to show details
                    node.on("click", (event, d) => {{
                        event.stopPropagation();
                        showDetails(d);
                        highlightConnections(d);
                    }});

                    // Click background to reset
                    svg.on("click", () => {{
                        closePanel();
                        resetHighlight();
                    }});

                    // Simulation tick
                    simulation.on("tick", () => {{
                        link
                            .attr("x1", d => d.source.x)
                            .attr("y1", d => d.source.y)
                            .attr("x2", d => d.target.x)
                            .attr("y2", d => d.target.y);

                        linkLabel
                            .attr("x", d => (d.source.x + d.target.x) / 2)
                            .attr("y", d => (d.source.y + d.target.y) / 2);

                        node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
                    }});

                    // Drag functions
                    function dragstarted(event, d) {{
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x; d.fy = d.y;
                    }}
                    function dragged(event, d) {{ d.fx = event.x; d.fy = event.y; }}
                    function dragended(event, d) {{
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null; d.fy = null;
                    }}


                    // Show detail panel
                    function showDetails(d) {{
                        const panel = document.getElementById("detail-panel");
                        const content = document.getElementById("panel-content");
                        
                        const badgeColors = {{
                            "Person": "#667eea",
                            "Commitment": "#f59e0b",
                            "Decision": "#10b981",
                        }};
                        const color = badgeColors[d.type] || "#94a3b8";
                        
                        let html = `<h3>${{d.label}}</h3>`;
                        html += `<span class="type-badge" style="background:${{color}}20;color:${{color}}">${{d.type}}</span>`;
                        
                        // Show all details
                        if (d.details) {{
                            for (const [key, value] of Object.entries(d.details)) {{
                                if (key === "id") continue;
                                const displayKey = key.replace(/_/g, " ").replace(/\\b\\w/g, l => l.toUpperCase());
                                html += `<div class="detail-row"><strong>${{displayKey}}:</strong> ${{value}}</div>`;
                            }}
                        }}
                        
                        // Show connections
                        const connections = data.links.filter(l => 
                            (l.source.id || l.source) === d.id || (l.target.id || l.target) === d.id
                        );
                        if (connections.length > 0) {{
                            html += `<div class="connections"><strong style="font-size:12px">Connections (${{connections.length}}):</strong>`;
                            connections.forEach(c => {{
                                const otherId = (c.source.id || c.source) === d.id ? (c.target.id || c.target) : (c.source.id || c.source);
                                const otherNode = data.nodes.find(n => n.id === otherId);
                                const otherLabel = otherNode ? otherNode.label : otherId;
                                const direction = (c.source.id || c.source) === d.id ? "\u2192" : "\u2190";
                                html += `<div class="conn-item">${{direction}} ${{c.relationship}} \u2014 ${{otherLabel}}</div>`;
                            }});
                            html += `</div>`;
                        }}
                        
                        content.innerHTML = html;
                        panel.classList.add("visible");
                    }}

                    function closePanel() {{
                        document.getElementById("detail-panel").classList.remove("visible");
                    }}


                    // Highlight connected nodes
                    function highlightConnections(d) {{
                        const connectedIds = new Set([d.id]);
                        data.links.forEach(l => {{
                            const srcId = l.source.id || l.source;
                            const tgtId = l.target.id || l.target;
                            if (srcId === d.id) connectedIds.add(tgtId);
                            if (tgtId === d.id) connectedIds.add(srcId);
                        }});

                        node.classed("dimmed", n => !connectedIds.has(n.id));
                        link.classed("dimmed", l => {{
                            const srcId = l.source.id || l.source;
                            const tgtId = l.target.id || l.target;
                            return srcId !== d.id && tgtId !== d.id;
                        }});
                        link.classed("highlighted", l => {{
                            const srcId = l.source.id || l.source;
                            const tgtId = l.target.id || l.target;
                            return srcId === d.id || tgtId === d.id;
                        }});
                    }}

                    function resetHighlight() {{
                        node.classed("dimmed", false);
                        link.classed("dimmed", false);
                        link.classed("highlighted", false);
                    }}
                </script>
            </body>
            </html>
            """

            import streamlit.components.v1 as components
            components.html(d3_html, height=560, scrolling=False)

        else:
            st.info("Graph is empty. Ingest a transcript to populate it!")
    else:
        st.info("Could not load graph data.")
