#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic Metadata Extraction using AI
Better metadata extraction for ChromaDB using GPT-4 and semantic understanding
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import openai

logger = logging.getLogger(__name__)


def extract_metadata_with_ai(
    text: str,
    summary: str,
    client: openai.OpenAI,
    filename: str = ""
) -> Dict:
    """
    Use AI to extract comprehensive metadata from meeting content

    Args:
        text: Original meeting transcript/text
        summary: AI-generated summary
        client: OpenAI client
        filename: Original filename for date extraction

    Returns:
        Dict with comprehensive metadata
    """

    try:
        # Create prompt for structured metadata extraction
        extraction_prompt = f"""Analyze this meeting content and extract structured metadata.

MEETING CONTENT:
{text[:3000]}  # First 3000 chars for context

MEETING SUMMARY:
{summary[:1500]}  # Summary for additional context

Extract the following information and return ONLY valid JSON:

{{
    "meeting_type": "one of: standup, planning, review, retrospective, brainstorm, decision, training, client, interview, general",
    "priority": "one of: high, medium, normal",
    "main_topics": ["topic1", "topic2", "topic3"],  // Max 5 key topics
    "participants": ["Name1", "Name2"],  // Actual names if found
    "key_decisions": ["decision1", "decision2"],  // Major decisions made
    "action_items": ["action1", "action2"],  // Specific action items
    "departments": ["dept1", "dept2"],  // Departments/teams mentioned
    "projects": ["project1"],  // Project names mentioned
    "has_budget_discussion": true/false,
    "sentiment": "one of: positive, neutral, negative, mixed",
    "urgency_indicators": ["urgent", "asap"] or [],
    "follow_up_required": true/false
}}

Rules:
- Use actual names/terms from the meeting, not generic placeholders
- Be specific and accurate
- If information is not found, use empty arrays or null
- Infer meeting_type from content
- Extract REAL topics, not generic ones"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise metadata extraction assistant. Always return valid JSON."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        ai_metadata = json.loads(response.choices[0].message.content)
        logger.info(f"✅ AI metadata extracted: {len(ai_metadata)} fields")

        # Validate and clean metadata
        metadata = {
            # Meeting Classification
            "meeting_type": ai_metadata.get("meeting_type", "general"),
            "priority": ai_metadata.get("priority", "normal"),
            "sentiment": ai_metadata.get("sentiment", "neutral"),

            # Content Analysis (store as strings for ChromaDB)
            "main_topics": ", ".join(ai_metadata.get("main_topics", [])[:5]),
            "participants": ", ".join(ai_metadata.get("participants", [])[:10]),
            "departments": ", ".join(ai_metadata.get("departments", [])[:5]),
            "projects": ", ".join(ai_metadata.get("projects", [])[:3]),

            # Decisions & Actions
            "key_decisions": ", ".join(ai_metadata.get("key_decisions", [])[:5]),
            "action_items_list": ", ".join(ai_metadata.get("action_items", [])[:10]),
            "action_items_count": len(ai_metadata.get("action_items", [])),

            # Flags
            "has_decisions": len(ai_metadata.get("key_decisions", [])) > 0,
            "has_action_items": len(ai_metadata.get("action_items", [])) > 0,
            "has_budget_discussion": ai_metadata.get("has_budget_discussion", False),
            "follow_up_required": ai_metadata.get("follow_up_required", False),
            "is_urgent": len(ai_metadata.get("urgency_indicators", [])) > 0,

            # Searchable keywords
            "urgency_indicators": ", ".join(ai_metadata.get("urgency_indicators", [])),
        }

        # Calculate derived metrics
        metadata["has_multiple_topics"] = len(ai_metadata.get("main_topics", [])) > 2
        metadata["has_multiple_participants"] = len(ai_metadata.get("participants", [])) > 2
        metadata["is_high_priority"] = metadata["priority"] == "high"
        metadata["is_actionable"] = metadata["action_items_count"] > 0

        logger.info(f"📋 Structured metadata created: {metadata['meeting_type']} meeting")
        logger.info(f"   Topics: {metadata['main_topics']}")
        logger.info(f"   Participants: {metadata['participants']}")
        logger.info(f"   Decisions: {len(ai_metadata.get('key_decisions', []))}")
        logger.info(f"   Actions: {metadata['action_items_count']}")

        return metadata

    except Exception as e:
        logger.error(f"❌ Error extracting AI metadata: {e}")

        # Fallback to basic metadata
        return {
            "meeting_type": "general",
            "priority": "normal",
            "sentiment": "neutral",
            "main_topics": "",
            "participants": "",
            "departments": "",
            "projects": "",
            "key_decisions": "",
            "action_items_list": "",
            "action_items_count": 0,
            "has_decisions": False,
            "has_action_items": False,
            "has_budget_discussion": False,
            "follow_up_required": False,
            "is_urgent": False,
            "urgency_indicators": "",
            "has_multiple_topics": False,
            "has_multiple_participants": False,
            "is_high_priority": False,
            "is_actionable": False
        }


def extract_enhanced_metrics(text: str, summary: str) -> Dict:
    """
    Extract additional metrics from text

    Args:
        text: Original text
        summary: Summary text

    Returns:
        Dict with metrics
    """

    import re

    metrics = {}

    # Text metrics
    metrics["text_length"] = len(text)
    metrics["summary_length"] = len(summary)
    metrics["word_count"] = len(text.split())
    metrics["summary_word_count"] = len(summary.split())

    # Estimate duration (150 words per minute speaking rate)
    metrics["estimated_duration_minutes"] = max(1, metrics["word_count"] // 150)
    metrics["is_long_meeting"] = metrics["estimated_duration_minutes"] > 60

    # Language detection (simple)
    vietnamese_chars = re.findall(r'[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]', text)
    metrics["language"] = "vi" if len(vietnamese_chars) / max(len(text), 1) > 0.05 else "en"

    # Structural analysis
    metrics["has_bullet_points"] = bool(re.search(r'[•\-\*]\s', text))
    metrics["has_numbers"] = bool(re.search(r'\d+', text))
    metrics["has_questions"] = bool(re.search(r'\?', text))

    return metrics


def create_searchable_content(
    summary: str,
    metadata: Dict,
    include_metadata_in_search: bool = True
) -> str:
    """
    Create enhanced searchable content by combining summary with key metadata

    This improves search by including important keywords from metadata

    Args:
        summary: Original summary
        metadata: Extracted metadata
        include_metadata_in_search: Whether to append metadata to searchable content

    Returns:
        Enhanced searchable content
    """

    if not include_metadata_in_search:
        return summary

    # Add key metadata terms to improve search
    searchable_parts = [summary]

    # Add topics as searchable keywords
    if metadata.get("main_topics"):
        searchable_parts.append(f"\nKey Topics: {metadata['main_topics']}")

    # Add important decisions (improves search for "decisions")
    if metadata.get("key_decisions"):
        searchable_parts.append(f"\nKey Decisions: {metadata['key_decisions']}")

    # Add project names (improves search by project)
    if metadata.get("projects"):
        searchable_parts.append(f"\nProjects: {metadata['projects']}")

    # Add departments (improves search by department)
    if metadata.get("departments"):
        searchable_parts.append(f"\nDepartments: {metadata['departments']}")

    enhanced_content = "\n".join(searchable_parts)

    logger.info(f"📄 Enhanced searchable content: {len(enhanced_content)} chars (original: {len(summary)})")

    return enhanced_content


def extract_date_from_filename(filename: str) -> str:
    """Extract date from filename patterns"""
    import re
    from datetime import datetime

    # Pattern: ddMMyyyy
    match = re.search(r'(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    # Pattern: yyyy-mm-dd or yyyy_mm_dd
    match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', filename)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    # Pattern: dd-mm-yyyy or dd_mm_yyyy
    match = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    # Fallback to current date
    return datetime.now().strftime("%Y-%m-%d")
