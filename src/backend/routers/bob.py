"""
Ask Bob API router for TrialGuard.

Provides a REST endpoint for the React frontend to get AI-generated responses.
Orchestrates deterministic intent routing, MCP tool calls, and NVIDIA Nemotron response generation.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.routers.mcp import (
    _tool_analyse_site_trends,
    _tool_get_patient_timeline,
    _tool_get_protocol_rule,
    _tool_get_site_risk_detail,
    _tool_query_deviations,
)
from src.backend.services.bob_response_generator import generate_bob_response
from src.backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bob", tags=["bob"])


# Tool map - same as MCP but for internal use
_TOOL_MAP = {
    "get_site_risk_detail": _tool_get_site_risk_detail,
    "query_deviations": _tool_query_deviations,
    "get_protocol_rule": _tool_get_protocol_rule,
    "analyse_site_trends": _tool_analyse_site_trends,
    "get_patient_timeline": _tool_get_patient_timeline,
}


def _parse_intent(query: str) -> tuple[str, dict[str, Any]] | tuple[None, str] | None:
    """
    Deterministic intent parser - maps natural language to MCP tools.
    
    Returns:
    - (tool_name, tool_args) for TrialGuard queries that need MCP tools
    - (None, "identity") for assistant identity questions
    - (None, "capability") for capability questions
    - (None, "unsupported") for unsupported questions
    - None for greetings (handled separately)
    """
    q = query.lower()

    # Handle greetings - return None to indicate no tool needed
    greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]
    if q.strip() in greetings or any(q.strip().startswith(g) for g in greetings):
        return None  # Greeting handled in response generator

    # Assistant identity questions
    identity_patterns = [
        "which ai assistant model are you",
        "what model are you",
        "what ai model powers you",
        "are you using nvidia",
        "what model powers trialguard",
        "who are you",
        "what is your name",
        "what assistant are you",
    ]
    if any(pattern in q for pattern in identity_patterns):
        return (None, "identity")

    # Capability questions
    capability_patterns = [
        "what can you do",
        "what can trialguard ai help me with",
        "how can you help",
        "what are your capabilities",
        "what can trialguard do",
    ]
    if any(pattern in q for pattern in capability_patterns):
        return (None, "capability")

    # Extract site ID from various formats
    def extract_site_id(text: str) -> str | None:
        import re
        upper_match = re.search(r"SITE-\d+", text, re.IGNORECASE)
        if upper_match:
            return upper_match[0].upper()
        space_match = re.search(r"site\s*(\d+)", text, re.IGNORECASE)
        if space_match:
            num = space_match.group(1).zfill(3)
            return f"SITE-{num}"
        return None

    # Extract patient ID from various formats
    def extract_patient_id(text: str) -> str | None:
        import re
        match = re.search(r"PT[-\s]*(\d+)", text, re.IGNORECASE)
        if match:
            num = match.group(1).zfill(4)
            return f"PT-{num}"
        return None

    # Site-specific risk questions
    if "site" in q and ("risk" in q or "why" in q or "detail" in q):
        site_id = extract_site_id(query)
        if site_id:
            return "get_site_risk_detail", {"site_id": site_id}

    # Deviation queries
    if "deviations" in q or "violations" in q:
        site_id = extract_site_id(query)
        patient_id = extract_patient_id(query)
        is_major = "major" in q
        is_minor = "minor" in q
        is_admin = "administrative" in q
        
        severity = None
        if is_major:
            severity = "Major"
        elif is_minor:
            severity = "Minor"
        elif is_admin:
            severity = "Administrative"
        
        return "query_deviations", {
            "site_id": site_id,
            "patient_id": patient_id,
            "severity": severity,
            "status": "Open",
        }

    # Patient-specific queries
    if "patient" in q or "timeline" in q or "have" in q:
        patient_id = extract_patient_id(query)
        if patient_id:
            if "deviations" in q or "violations" in q:
                return "query_deviations", {"patient_id": patient_id, "status": "Open"}
            return "get_patient_timeline", {"patient_id": patient_id}

    # Trial-wide summaries
    if "trend" in q or "all site" in q or "summarise all site" in q:
        return "analyse_site_trends", {}

    # Protocol rule queries
    if "rule" in q:
        import re
        match = re.search(r"(INC|EXC|LAB|DOS|REP)[-–\s]*(\d+)", query, re.IGNORECASE)
        if match:
            prefix = match.group(1).upper()
            num = match.group(2).zfill(2)
            return "get_protocol_rule", {"rule_id": f"{prefix}-{num}"}

    # "Summarise all site risk scores"
    if "summarise" in q and "site" in q and "risk" in q:
        return "analyse_site_trends", {}

    # Default: unsupported question - do NOT call any MCP tool
    return (None, "unsupported")


@router.post("/ask")
async def ask_bob(
    request: dict[str, str],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ask Bob endpoint for the React frontend.
    
    Takes a user question, routes to the appropriate MCP tool,
    and returns an AI-generated response using NVIDIA Nemotron
    (or deterministic fallback if NVIDIA is unavailable).
    """
    user_question = request.get("question", "").strip()
    if not user_question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Parse intent and select tool
    intent = _parse_intent(user_question)
    
    # Handle greetings - no tool needed
    if intent is None:
        try:
            response_text, source = generate_bob_response(
                user_question=user_question,
                tool_name="greeting",
                tool_result={},
            )
        except Exception as exc:
            logger.error("Response generation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Response generation failed: {exc}"
            ) from exc
        
        return {
            "response": response_text,
            "source": source,
            "tool_used": "none",
        }
    
    # Handle non-tool intents (identity, capability, unsupported)
    if intent[0] is None:
        intent_type = intent[1]
        try:
            response_text, source = generate_bob_response(
                user_question=user_question,
                tool_name=intent_type,
                tool_result={},
            )
        except Exception as exc:
            logger.error("Response generation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Response generation failed: {exc}"
            ) from exc
        
        return {
            "response": response_text,
            "source": source,
            "tool_used": "none",
        }
    
    tool_name, tool_args = intent

    # Call the MCP tool
    if tool_name not in _TOOL_MAP:
        raise HTTPException(
            status_code=500,
            detail=f"Tool '{tool_name}' not available"
        )

    try:
        tool_result = _TOOL_MAP[tool_name](db, tool_args)
    except Exception as exc:
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution failed: {exc}"
        ) from exc

    # Generate response with NVIDIA or fallback
    try:
        response_text, source = generate_bob_response(
            user_question=user_question,
            tool_name=tool_name,
            tool_result=tool_result,
        )
    except Exception as exc:
        logger.error("Response generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Response generation failed: {exc}"
        ) from exc

    return {
        "response": response_text,
        "source": source,
        "tool_used": tool_name,
    }
