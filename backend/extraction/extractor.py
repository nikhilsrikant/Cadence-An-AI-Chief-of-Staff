"""
Cadence - Commitment Extraction Engine
Uses IBM watsonx.ai Granite model to extract structured commitments
and decisions from unstructured text.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from backend.extraction.prompts import (
    SYSTEM_PROMPT,
    EXTRACTION_PROMPT,
    CONTEXT_SECTION_MEETING,
    CONTEXT_SECTION_SLACK,
    CONTEXT_SECTION_CALENDAR,
)
from backend.models.schemas import (
    Commitment,
    CommitmentStatus,
    Decision,
    ExtractionResult,
    Priority,
    SourceType,
    TranscriptInput,
)
from backend.utils.logger import logger


class CommitmentExtractor:
    """
    Extracts structured commitments and decisions from unstructured text
    using IBM watsonx.ai Granite foundation model.
    """

    def __init__(self):
        self._model = None
        self._initialized = False

    def _init_model(self):
        """Lazy-initialize the watsonx.ai model."""
        if self._initialized:
            return

        try:
            from ibm_watsonx_ai.foundation_models import Model
            from ibm_watsonx_ai.metanames import GenTextParamsMetaNames
            from config.settings import settings

            params = {
                GenTextParamsMetaNames.MAX_NEW_TOKENS: settings.extraction_max_tokens,
                GenTextParamsMetaNames.TEMPERATURE: settings.extraction_temperature,
                GenTextParamsMetaNames.TOP_P: 0.95,
                GenTextParamsMetaNames.REPETITION_PENALTY: 1.05,
            }

            self._model = Model(
                model_id=settings.granite_model_id,
                credentials={
                    "apikey": settings.watsonx_api_key,
                    "url": settings.watsonx_url,
                },
                project_id=settings.watsonx_project_id,
                params=params,
            )
            self._initialized = True
            logger.info(f"watsonx.ai model initialized: {settings.granite_model_id}")
        except Exception as e:
            logger.warning(f"Could not initialize watsonx.ai model: {e}")
            logger.info("Falling back to local extraction mode")
            self._initialized = True  # Mark as initialized to avoid retries

    def _get_context_section(self, input_data: TranscriptInput) -> str:
        """Build the context section for the prompt based on source type."""
        participants = ", ".join(input_data.participants) if input_data.participants else "Unknown"

        if input_data.source_type == SourceType.MEETING_TRANSCRIPT:
            return CONTEXT_SECTION_MEETING.format(
                meeting_title=input_data.meeting_title or "Untitled Meeting",
                participants=participants,
            )
        elif input_data.source_type == SourceType.SLACK_THREAD:
            return CONTEXT_SECTION_SLACK.format(participants=participants)
        else:
            return CONTEXT_SECTION_CALENDAR.format(participants=participants)

    def _build_prompt(self, input_data: TranscriptInput) -> str:
        """Build the full extraction prompt."""
        source_type_label = {
            SourceType.MEETING_TRANSCRIPT: "meeting transcript",
            SourceType.SLACK_THREAD: "Slack thread",
            SourceType.CALENDAR_INVITE: "calendar invite",
        }

        context_section = self._get_context_section(input_data)

        return EXTRACTION_PROMPT.format(
            source_type=source_type_label.get(input_data.source_type, "text"),
            context_section=context_section,
            text=input_data.text,
        )

    def _call_model(self, prompt: str) -> str:
        """Call the watsonx.ai model or fall back to local parsing."""
        self._init_model()

        if self._model:
            try:
                full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
                response = self._model.generate_text(full_prompt)
                return response
            except Exception as e:
                logger.error(f"Model call failed: {e}")
                return self._fallback_extract(prompt)
        else:
            return self._fallback_extract(prompt)

    def _fallback_extract(self, prompt: str) -> str:
        """
        Fallback extraction using keyword-based heuristics.
        Used when watsonx.ai is unavailable (demo/dev mode).
        """
        # Extract the text between markers
        text = ""
        if "--- TEXT TO ANALYZE ---" in prompt:
            parts = prompt.split("--- TEXT TO ANALYZE ---")
            if len(parts) > 1:
                text = parts[1].split("--- END TEXT ---")[0].strip()

        return self._heuristic_extract(text)

    def _heuristic_extract(self, text: str) -> str:
        """
        Simple heuristic extraction for demo/development mode.
        Identifies commitments by looking for action patterns.
        """
        lines = text.split("\n")
        commitments = []
        decisions = []

        action_keywords = [
            "will", "going to", "needs to", "should", "must",
            "take care of", "handle", "own", "responsible for",
            "action item", "todo", "to-do", "follow up", "deliver",
            "by end of", "by friday", "by monday", "by next week",
            "deadline", "due date", "complete by",
        ]

        decision_keywords = [
            "decided", "agreed", "we'll go with", "let's go with",
            "final decision", "we chose", "approved", "selected",
            "moving forward with", "the plan is",
        ]

        deadline_keywords = {
            "by end of week": "friday",
            "by friday": "friday",
            "by monday": "monday",
            "by next week": "next week",
            "asap": "urgent",
            "urgent": "urgent",
            "eod": "today",
            "end of day": "today",
        }

        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower or len(line_lower) < 10:
                continue

            # Check for commitments
            is_commitment = any(kw in line_lower for kw in action_keywords)
            if is_commitment:
                # Try to extract owner (look for names - capitalized words)
                words = line.split()
                owner = "Unassigned"
                for i, word in enumerate(words):
                    if word[0].isupper() and word.isalpha() and len(word) > 2:
                        # Look for "Name will..." or "...by Name"
                        if i + 1 < len(words) and words[i + 1].lower() in ["will", "should", "needs", "is"]:
                            owner = word
                            break
                        if i > 0 and words[i - 1].lower() in ["by", "to", "for"]:
                            owner = word
                            break

                # Determine priority
                priority = "medium"
                if any(kw in line_lower for kw in ["asap", "urgent", "critical", "blocker"]):
                    priority = "high"
                elif any(kw in line_lower for kw in ["nice to have", "eventually", "low priority"]):
                    priority = "low"

                commitments.append({
                    "title": line.strip()[:80],
                    "description": line.strip(),
                    "owner_name": owner,
                    "deadline": None,
                    "priority": priority,
                    "dependencies": [],
                })

            # Check for decisions
            is_decision = any(kw in line_lower for kw in decision_keywords)
            if is_decision:
                decisions.append({
                    "title": line.strip()[:80],
                    "description": line.strip(),
                    "made_by": "Team",
                })

        return json.dumps({"commitments": commitments, "decisions": decisions})

    def _parse_response(self, response: str, input_data: TranscriptInput) -> ExtractionResult:
        """Parse the model's JSON response into structured objects."""
        try:
            # Try to extract JSON from the response
            json_str = response.strip()

            # Handle cases where model wraps JSON in markdown
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return ExtractionResult(
                commitments=[],
                decisions=[],
                source_type=input_data.source_type,
            )

        # Parse commitments
        commitments: List[Commitment] = []
        for item in data.get("commitments", []):
            try:
                deadline = None
                if item.get("deadline"):
                    try:
                        deadline = datetime.strptime(item["deadline"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass

                priority_map = {
                    "low": Priority.LOW,
                    "medium": Priority.MEDIUM,
                    "high": Priority.HIGH,
                    "critical": Priority.CRITICAL,
                }

                commitment = Commitment(
                    id=str(uuid4()),
                    title=item.get("title", "Untitled"),
                    description=item.get("description"),
                    owner_name=item.get("owner_name", "Unassigned"),
                    deadline=deadline,
                    status=CommitmentStatus.PENDING,
                    priority=priority_map.get(item.get("priority", "medium"), Priority.MEDIUM),
                    dependencies=item.get("dependencies", []),
                    source_type=input_data.source_type,
                    meeting_title=input_data.meeting_title,
                )
                commitments.append(commitment)
            except Exception as e:
                logger.warning(f"Failed to parse commitment: {e}")
                continue

        # Parse decisions
        decisions: List[Decision] = []
        for item in data.get("decisions", []):
            try:
                decision = Decision(
                    id=str(uuid4()),
                    title=item.get("title", "Untitled Decision"),
                    description=item.get("description"),
                    made_by=item.get("made_by", "Unknown"),
                    source_type=input_data.source_type,
                )
                decisions.append(decision)
            except Exception as e:
                logger.warning(f"Failed to parse decision: {e}")
                continue

        return ExtractionResult(
            commitments=commitments,
            decisions=decisions,
            source_type=input_data.source_type,
        )

    def extract(self, input_data: TranscriptInput) -> ExtractionResult:
        """
        Main extraction method. Takes unstructured text and returns
        structured commitments and decisions.
        """
        logger.info(
            f"Extracting from {input_data.source_type.value}: "
            f"{len(input_data.text)} chars, {len(input_data.participants)} participants"
        )

        prompt = self._build_prompt(input_data)
        response = self._call_model(prompt)
        result = self._parse_response(response, input_data)

        logger.info(
            f"Extracted {len(result.commitments)} commitments, "
            f"{len(result.decisions)} decisions"
        )

        return result


# Singleton
_extractor: Optional[CommitmentExtractor] = None


def get_extractor() -> CommitmentExtractor:
    """Get the global extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = CommitmentExtractor()
    return _extractor
