"""
IBM Bob MCP Server for TrialGuard.

Implements a JSON-RPC 2.0 endpoint at POST /mcp that IBM Bob can call
as a Model Context Protocol (MCP) tool server.

Supported methods:
    tools/list                  — list all available tools
    tools/call                  — invoke a specific tool

Available tools:
    get_site_risk_detail        — risk score breakdown for a site
    query_deviations            — filtered deviation list
    generate_capa               — trigger CAPA generation for a deviation
    get_protocol_rule           — protocol rule definition + violation count
    analyse_site_trends         — cross-site deviation trend summary
    get_patient_timeline        — ordered visit + deviation timeline

All tools return structured JSON.  IBM Bob's model processes this JSON and
produces a natural-language narrative for the user.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import (
    CAPA,
    CAPAStatus,
    AdverseEvent,
    Deviation,
    DeviationSeverity,
    DeviationStatus,
    Patient,
    Site,
    SiteRiskScore,
    Visit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_site_risk_detail",
        "description": (
            "Return the latest risk score breakdown for a clinical trial site, "
            "including open deviation counts by severity, CAPA status, "
            "and enrollment figures. Use this to explain why a site is at a "
            "given risk tier."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {
                    "type": "string",
                    "description": "Site identifier, e.g. SITE-003",
                }
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "query_deviations",
        "description": (
            "Return a filtered list of protocol deviations. "
            "Supports filtering by site, patient, severity, and status. "
            "Use this to enumerate compliance issues at a site or for a patient."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Filter by site ID"},
                "patient_id": {"type": "string", "description": "Filter by patient ID"},
                "severity": {
                    "type": "string",
                    "enum": ["Major", "Minor", "Administrative"],
                    "description": "Filter by severity level",
                },
                "status": {
                    "type": "string",
                    "enum": ["Open", "Closed", "Pending Review"],
                    "description": "Filter by status",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "generate_capa",
        "description": (
            "Generate a CAPA (Corrective and Preventive Action) narrative for a "
            "specific deviation using watsonx.ai. Returns a structured CAPA text "
            "with root cause analysis, corrective action, and preventive action."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "deviation_id": {
                    "type": "integer",
                    "description": "The numeric ID of the deviation to generate CAPA for",
                }
            },
            "required": ["deviation_id"],
        },
    },
    {
        "name": "get_protocol_rule",
        "description": (
            "Return the definition of a protocol rule and how many times it has "
            "been violated. Use this to explain what a specific rule requires "
            "and its compliance status across the trial."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "string",
                    "description": "Rule identifier, e.g. INC-01, LAB-02, REP-01",
                }
            },
            "required": ["rule_id"],
        },
    },
    {
        "name": "analyse_site_trends",
        "description": (
            "Return a cross-site summary of deviation trends. Shows all sites "
            "ranked by risk score with deviation counts and tier. Optionally "
            "filter by deviation type keyword."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "deviation_type": {
                    "type": "string",
                    "description": "Optional keyword to filter by deviation type",
                }
            },
        },
    },
    {
        "name": "get_patient_timeline",
        "description": (
            "Return a patient's full visit history with deviations attached "
            "to each visit. Shows protocol adherence visit by visit. "
            "Use this to explain a patient's compliance status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "Patient identifier, e.g. PT-0042",
                }
            },
            "required": ["patient_id"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────

def _tool_get_site_risk_detail(db: Session, args: dict) -> dict:
    site_id = args.get("site_id", "")
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return {"error": f"Site {site_id} not found"}

    risk = (
        db.query(SiteRiskScore)
        .filter(SiteRiskScore.site_id == site_id)
        .order_by(SiteRiskScore.score_date.desc())
        .first()
    )

    open_capas = db.query(func.count(CAPA.id)).filter(
        CAPA.site_id == site_id, CAPA.status != CAPAStatus.CLOSED
    ).scalar()

    closed_capas = db.query(func.count(CAPA.id)).filter(
        CAPA.site_id == site_id, CAPA.status == CAPAStatus.CLOSED
    ).scalar()

    # Top 5 most recent open deviations
    recent_devs = (
        db.query(Deviation)
        .filter(Deviation.site_id == site_id, Deviation.status == DeviationStatus.OPEN)
        .order_by(Deviation.detected_date.desc())
        .limit(5)
        .all()
    )

    return {
        "site_id": site.id,
        "site_name": site.name,
        "city": site.city,
        "country": site.country,
        "principal_investigator": site.principal_investigator,
        "enrolled": site.enrolled_count,
        "target_enrollment": site.target_enrollment,
        "risk_score": risk.total_score if risk else None,
        "risk_tier": risk.risk_tier.value if risk else None,
        "score_date": str(risk.score_date) if risk else None,
        "open_major_deviations": risk.major_open_count if risk else 0,
        "open_minor_deviations": risk.minor_open_count if risk else 0,
        "open_admin_deviations": risk.admin_open_count if risk else 0,
        "avg_capa_age_days": risk.avg_capa_age_days if risk else 0,
        "data_query_rate_pct": risk.data_query_rate_pct if risk else 0,
        "enrollment_deviation_pct": risk.enrollment_deviation_pct if risk else 0,
        "open_capas": open_capas,
        "closed_capas": closed_capas,
        "score_components": {
            "major_contribution": risk.major_open_count * 10 if risk else 0,
            "minor_contribution": risk.minor_open_count * 3 if risk else 0,
            "capa_age_contribution": round((risk.avg_capa_age_days / 30) * 5, 1) if risk else 0,
        },
        "recent_open_deviations": [
            {
                "id": d.id,
                "patient_id": d.patient_id,
                "rule_id": d.rule_id,
                "severity": d.severity.value,
                "deviation_type": d.deviation_type,
                "detected_date": str(d.detected_date),
            }
            for d in recent_devs
        ],
    }


def _tool_query_deviations(db: Session, args: dict) -> dict:
    q = db.query(Deviation)
    if args.get("site_id"):
        q = q.filter(Deviation.site_id == args["site_id"])
    if args.get("patient_id"):
        q = q.filter(Deviation.patient_id == args["patient_id"])
    if args.get("severity"):
        # Map string to enum
        severity_map = {
            "Major": DeviationSeverity.MAJOR,
            "Minor": DeviationSeverity.MINOR,
            "Administrative": DeviationSeverity.ADMINISTRATIVE,
        }
        severity_val = severity_map.get(args["severity"])
        if severity_val:
            q = q.filter(Deviation.severity == severity_val)
    if args.get("status"):
        # Map string to enum
        status_map = {
            "Open": DeviationStatus.OPEN,
            "Closed": DeviationStatus.CLOSED,
            "Pending Review": DeviationStatus.PENDING_REVIEW,
        }
        status_val = status_map.get(args["status"])
        if status_val:
            q = q.filter(Deviation.status == status_val)

    limit = min(int(args.get("limit", 20)), 100)
    devs = q.order_by(Deviation.detected_date.desc()).limit(limit).all()

    return {
        "count": len(devs),
        "deviations": [
            {
                "id": d.id,
                "patient_id": d.patient_id,
                "site_id": d.site_id,
                "rule_id": d.rule_id,
                "severity": d.severity.value,
                "status": d.status.value,
                "deviation_type": d.deviation_type,
                "description": d.description,
                "detected_date": str(d.detected_date),
            }
            for d in devs
        ],
    }


def _tool_generate_capa(db: Session, args: dict) -> dict:
    dev_id = args.get("deviation_id")
    dev = db.query(Deviation).filter(Deviation.id == dev_id).first()
    if not dev:
        return {"error": f"Deviation {dev_id} not found"}

    from src.backend.services.capa_generator import generate_capa_narrative

    narrative, source = generate_capa_narrative(db, dev)

    # Upsert CAPA record
    capa = db.query(CAPA).filter(CAPA.deviation_id == dev.id).first()
    if not capa:
        capa = CAPA(
            deviation_id=dev.id,
            site_id=dev.site_id,
            status=CAPAStatus.OPEN,
            watsonx_narrative=narrative,
        )
        db.add(capa)
    else:
        capa.watsonx_narrative = narrative
    db.commit()
    db.refresh(capa)

    return {
        "capa_id": capa.id,
        "deviation_id": dev.id,
        "patient_id": dev.patient_id,
        "site_id": dev.site_id,
        "deviation_type": dev.deviation_type,
        "severity": dev.severity,
        "source": source,
        "narrative": narrative,
    }


def _tool_get_protocol_rule(db: Session, args: dict) -> dict:
    rule_id = args.get("rule_id", "")
    if not rule_id:
        return {"error": "rule_id is required"}

    from src.backend.engine.protocol_loader import get_protocol

    try:
        proto = get_protocol()
    except Exception as exc:
        return {"error": f"Protocol not loaded: {exc}"}

    # Look up rule in the flat rules dict (case-insensitive)
    rule_def = None
    for rid, rule in proto.rules.items():
        if rid.upper() == rule_id.upper():
            rule_def = rule
            rule_id = rid  # use canonical casing
            break

    if not rule_def:
        return {
            "error": f"Rule {rule_id} not found in protocol",
            "known_rule_ids": list(proto.rules.keys()),
        }

    # Count violations (use DeviationStatus.OPEN — the actual enum value)
    violation_count = (
        db.query(func.count(Deviation.id))
        .filter(Deviation.rule_id == rule_id, Deviation.status == DeviationStatus.OPEN)
        .scalar()
    )

    return {
        "rule_id": rule_def.rule_id,
        "category": rule_def.category,
        "description": rule_def.description,
        "severity_if_violated": rule_def.severity_if_violated,
        "open_violation_count": violation_count,
        "extra": rule_def.extra,
    }


def _tool_analyse_site_trends(db: Session, args: dict) -> dict:
    dev_type_filter = args.get("deviation_type")

    sites = db.query(Site).order_by(Site.id).all()
    results = []

    for site in sites:
        risk = (
            db.query(SiteRiskScore)
            .filter(SiteRiskScore.site_id == site.id)
            .order_by(SiteRiskScore.score_date.desc())
            .first()
        )

        q = db.query(func.count(Deviation.id)).filter(
            Deviation.site_id == site.id,
            Deviation.status == DeviationStatus.OPEN,
        )
        if dev_type_filter:
            q = q.filter(Deviation.deviation_type.ilike(f"%{dev_type_filter}%"))
        dev_count = q.scalar()

        results.append({
            "site_id": site.id,
            "site_name": site.name,
            "city": site.city,
            "country": site.country,
            "risk_tier": risk.risk_tier.value if risk else "UNKNOWN",
            "risk_score": risk.total_score if risk else None,
            "open_deviations_matching_filter": dev_count,
            "open_major": risk.major_open_count if risk else 0,
            "open_minor": risk.minor_open_count if risk else 0,
            "enrolled": site.enrolled_count,
            "target_enrollment": site.target_enrollment,
        })

    # Sort by risk score descending
    results.sort(key=lambda x: (x["risk_score"] or 0), reverse=True)

    return {
        "filter_applied": dev_type_filter,
        "total_sites": len(results),
        "sites": results,
    }


def _tool_get_patient_timeline(db: Session, args: dict) -> dict:
    patient_id = args.get("patient_id", "")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return {"error": f"Patient {patient_id} not found"}

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_number)
        .all()
    )

    all_deviations = (
        db.query(Deviation)
        .filter(Deviation.patient_id == patient_id)
        .order_by(Deviation.detected_date)
        .all()
    )

    dev_by_visit: dict[int | None, list] = {}
    for dev in all_deviations:
        dev_by_visit.setdefault(dev.visit_id, []).append(dev)

    timeline = []
    for v in visits:
        visit_devs = dev_by_visit.get(v.id, [])
        timeline.append({
            "visit_number": v.visit_number,
            "visit_name": v.visit_name,
            "scheduled_date": str(v.scheduled_date),
            "actual_date": str(v.actual_date) if v.actual_date else None,
            "window_deviation_days": v.window_deviation_days,
            "deviations": [
                {
                    "id": d.id,
                    "rule_id": d.rule_id,
                    "severity": d.severity,
                    "status": d.status,
                    "deviation_type": d.deviation_type,
                    "description": d.description,
                    "detected_date": str(d.detected_date),
                }
                for d in visit_devs
            ],
        })

    # Non-visit deviations (eligibility, etc.)
    non_visit_devs = [
        {
            "id": d.id,
            "rule_id": d.rule_id,
            "severity": d.severity,
            "status": d.status,
            "deviation_type": d.deviation_type,
            "description": d.description,
            "detected_date": str(d.detected_date),
        }
        for d in dev_by_visit.get(None, [])
    ]

    return {
        "patient_id": patient.id,
        "site_id": patient.site_id,
        "age": patient.age,
        "sex": patient.sex,
        "status": patient.status,
        "enrollment_date": str(patient.enrollment_date),
        "total_open_deviations": len([d for d in all_deviations if d.status == DeviationStatus.OPEN]),
        "visits": timeline,
        "non_visit_deviations": non_visit_devs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_MAP = {
    "get_site_risk_detail": _tool_get_site_risk_detail,
    "query_deviations": _tool_query_deviations,
    "generate_capa": _tool_generate_capa,
    "get_protocol_rule": _tool_get_protocol_rule,
    "analyse_site_trends": _tool_analyse_site_trends,
    "get_patient_timeline": _tool_get_patient_timeline,
}


def _jsonrpc_error(code: int, message: str, req_id: Any = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _jsonrpc_ok(result: Any, req_id: Any = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MCP endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("")
async def mcp_endpoint(request: Request, db: Session = Depends(get_db)):
    """
    Handle MCP JSON-RPC 2.0 requests from IBM Bob.

    Supported methods:
        tools/list  — returns the list of available tool definitions
        tools/call  — invokes a tool by name with provided arguments
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_jsonrpc_error(-32700, "Parse error"))

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tools/list":
        return JSONResponse(_jsonrpc_ok({"tools": TOOLS}, req_id))

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", params.get("input", {}))

        if tool_name not in _TOOL_MAP:
            return JSONResponse(
                _jsonrpc_error(
                    -32601,
                    f"Tool '{tool_name}' not found. Available: {list(_TOOL_MAP.keys())}",
                    req_id,
                )
            )

        try:
            result = _TOOL_MAP[tool_name](db, tool_args)
            return JSONResponse(
                _jsonrpc_ok(
                    {
                        "content": [
                            {"type": "text", "text": str(result)},
                            {"type": "json", "data": result},
                        ]
                    },
                    req_id,
                )
            )
        except Exception as exc:
            logger.error("MCP tool %s failed: %s", tool_name, exc, exc_info=True)
            return JSONResponse(
                _jsonrpc_error(-32603, f"Tool execution error: {exc}", req_id)
            )

    else:
        return JSONResponse(
            _jsonrpc_error(-32601, f"Method '{method}' not found", req_id)
        )
