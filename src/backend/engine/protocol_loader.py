"""
Protocol loader for TrialGuard.

Parses and validates src/backend/data/protocol.json (or any override path)
into strongly-typed dataclasses that the deviation engine and risk scorer can
consume without touching JSON again.

Design decisions
----------------
* Dataclasses are used (not Pydantic) to avoid pulling in extra dependencies
  at the engine layer and to keep the loader importable without FastAPI.
* All validation is eager: a malformed protocol raises ProtocolLoadError
  immediately rather than silently producing wrong deviations later.
* Rules from all sections are indexed by rule_id in a single flat dict for
  O(1) lookup during deviation classification.
* The loader is a module-level cached singleton (load_protocol / get_protocol)
  so the file is parsed once per process.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.backend.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class ProtocolLoadError(ValueError):
    """Raised when the protocol JSON is missing, malformed, or fails validation."""


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

VALID_SEVERITIES: frozenset[str] = frozenset({"Major", "Minor", "Administrative"})
VALID_OPERATORS: frozenset[str] = frozenset({"between", "eq", "lte", "gte", "lt", "gt"})


@dataclass(frozen=True)
class ProtocolRule:
    """A single rule from any section of the protocol (inclusion, lab, dosing, etc.)."""

    rule_id: str
    description: str
    severity_if_violated: str
    category: str
    """One of: 'inclusion', 'exclusion', 'lab', 'dosing', 'reporting', 'visit_window',
    'missing_assessment'."""
    extra: dict[str, Any] = field(default_factory=dict)
    """Holds category-specific fields (field, operator, values, test_name, etc.)."""

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ProtocolLoadError("Rule must have a non-empty rule_id")
        if self.severity_if_violated not in VALID_SEVERITIES:
            raise ProtocolLoadError(
                f"Rule {self.rule_id!r} has invalid severity "
                f"{self.severity_if_violated!r}. Must be one of {sorted(VALID_SEVERITIES)}."
            )


@dataclass(frozen=True)
class VisitSpec:
    """Protocol-defined visit with window tolerances and required assessments."""

    visit_number: int
    name: str
    nominal_day: int
    window_days_before: int
    window_days_after: int
    required_assessments: tuple[str, ...]

    def within_window(self, deviation_days: int) -> bool:
        """Return True if *deviation_days* is within the allowed window.

        Positive deviation = late, negative = early.
        """
        return (
            -self.window_days_before <= deviation_days <= self.window_days_after
        )


@dataclass
class Protocol:
    """
    Fully-loaded, validated trial protocol.

    Attributes
    ----------
    trial_id : str
    version  : str
    title    : str
    visits   : dict mapping visit_number -> VisitSpec
    rules    : flat dict mapping rule_id -> ProtocolRule
    severity_definitions : dict mapping severity label -> description text
    """

    trial_id: str
    version: str
    title: str
    visits: dict[int, VisitSpec]
    rules: dict[str, ProtocolRule]
    severity_definitions: dict[str, str]

    # ── Convenience helpers ──────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> ProtocolRule:
        """Return the rule for *rule_id* or raise KeyError."""
        try:
            return self.rules[rule_id]
        except KeyError:
            raise KeyError(f"Rule {rule_id!r} not found in protocol {self.trial_id!r}")

    def severity_for(self, rule_id: str) -> str:
        """Return the severity string for *rule_id*."""
        return self.get_rule(rule_id).severity_if_violated

    def visit(self, visit_number: int) -> VisitSpec:
        """Return the VisitSpec for *visit_number* or raise KeyError."""
        try:
            return self.visits[visit_number]
        except KeyError:
            raise KeyError(f"Visit number {visit_number} not found in protocol")

    def rules_by_category(self, category: str) -> list[ProtocolRule]:
        """Return all rules with the given category."""
        return [r for r in self.rules.values() if r.category == category]


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require(d: dict, key: str, context: str) -> Any:
    """Return d[key] or raise ProtocolLoadError if missing or empty."""
    val = d.get(key)
    if val is None or val == "":
        raise ProtocolLoadError(f"Missing required field {key!r} in {context}")
    return val


def _parse_eligibility_rules(
    raw_rules: list[dict],
    category: str,
) -> list[ProtocolRule]:
    """Parse inclusion or exclusion criteria into ProtocolRule objects."""
    rules: list[ProtocolRule] = []
    for raw in raw_rules:
        rule_id = _require(raw, "rule_id", f"{category} rule")
        description = _require(raw, "description", f"rule {rule_id}")
        severity = _require(raw, "severity_if_violated", f"rule {rule_id}")
        extra: dict[str, Any] = {}
        for k in ("field", "operator", "value", "values", "unit", "rationale"):
            if k in raw:
                extra[k] = raw[k]
        rules.append(ProtocolRule(
            rule_id=rule_id,
            description=description,
            severity_if_violated=severity,
            category=category,
            extra=extra,
        ))
    return rules


def _parse_lab_rules(raw_rules: list[dict]) -> list[ProtocolRule]:
    """Parse lab_thresholds into ProtocolRule objects."""
    rules: list[ProtocolRule] = []
    for raw in raw_rules:
        rule_id = _require(raw, "rule_id", "lab_threshold rule")
        description = raw.get("display_name") or raw.get("test_name") or rule_id
        severity = _require(raw, "severity_if_violated", f"rule {rule_id}")
        test_name = _require(raw, "test_name", f"lab rule {rule_id}")
        min_val = raw.get("min_value")   # may be None
        max_val = raw.get("max_value")   # may be None
        if min_val is None and max_val is None:
            raise ProtocolLoadError(
                f"Lab rule {rule_id!r} must have at least one of min_value or max_value"
            )
        rules.append(ProtocolRule(
            rule_id=rule_id,
            description=f"{description}: threshold violation",
            severity_if_violated=severity,
            category="lab",
            extra={
                "test_name": test_name,
                "display_name": raw.get("display_name", test_name),
                "min_value": min_val,
                "max_value": max_val,
                "unit": raw.get("unit", ""),
                "action_required": raw.get("action_required", ""),
                "rationale": raw.get("rationale", ""),
            },
        ))
    return rules


def _parse_dosing_rules(raw_rules: list[dict]) -> list[ProtocolRule]:
    """Parse dosing_rules into ProtocolRule objects."""
    rules: list[ProtocolRule] = []
    for raw in raw_rules:
        rule_id = _require(raw, "rule_id", "dosing rule")
        description = _require(raw, "description", f"rule {rule_id}")
        severity = _require(raw, "severity_if_violated", f"rule {rule_id}")
        extra: dict[str, Any] = {}
        for k in ("field", "operator", "value", "unit", "rationale"):
            if k in raw:
                extra[k] = raw[k]
        rules.append(ProtocolRule(
            rule_id=rule_id,
            description=description,
            severity_if_violated=severity,
            category="dosing",
            extra=extra,
        ))
    return rules


def _parse_reporting_rules(raw_rules: list[dict]) -> list[ProtocolRule]:
    """Parse reporting_rules into ProtocolRule objects."""
    rules: list[ProtocolRule] = []
    for raw in raw_rules:
        rule_id = _require(raw, "rule_id", "reporting rule")
        description = _require(raw, "description", f"rule {rule_id}")
        severity = _require(raw, "severity_if_violated", f"rule {rule_id}")
        extra: dict[str, Any] = {}
        for k in ("field", "operator", "value", "unit", "rationale"):
            if k in raw:
                extra[k] = raw[k]
        rules.append(ProtocolRule(
            rule_id=rule_id,
            description=description,
            severity_if_violated=severity,
            category="reporting",
            extra=extra,
        ))
    return rules


def _parse_visit_schedule(raw_visits: list[dict]) -> dict[int, VisitSpec]:
    """Parse visit_schedule array into a dict keyed by visit_number."""
    visits: dict[int, VisitSpec] = {}
    for raw in raw_visits:
        vnum = _require(raw, "visit_number", "visit schedule entry")
        assessments = _require(raw, "required_assessments", f"visit {vnum}")
        if not isinstance(assessments, list):
            raise ProtocolLoadError(f"Visit {vnum} required_assessments must be a list")
        visits[vnum] = VisitSpec(
            visit_number=vnum,
            name=raw.get("name", f"Visit {vnum}"),
            nominal_day=raw.get("nominal_day", 0),
            window_days_before=_require(raw, "window_days_before", f"visit {vnum}"),
            window_days_after=_require(raw, "window_days_after", f"visit {vnum}"),
            required_assessments=tuple(assessments),
        )
    return visits


# ─────────────────────────────────────────────────────────────────────────────
# Main loader
# ─────────────────────────────────────────────────────────────────────────────

def load_protocol(path: str | Path | None = None) -> Protocol:
    """
    Load, parse, and validate a protocol JSON file.

    Parameters
    ----------
    path : str or Path, optional
        Override the default path from settings.protocol_path.

    Returns
    -------
    Protocol
        Fully validated protocol object.

    Raises
    ------
    ProtocolLoadError
        If the file is missing, cannot be parsed as JSON, or fails structural
        validation.
    """
    resolved = Path(path) if path else Path(settings.protocol_path)

    if not resolved.exists():
        raise ProtocolLoadError(f"Protocol file not found: {resolved}")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProtocolLoadError(f"Protocol file is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ProtocolLoadError("Protocol file must be a JSON object at the top level")

    # ── Required top-level fields ────────────────────────────────────────────
    trial_id = _require(raw, "trial_id", "protocol root")
    version  = _require(raw, "version",  "protocol root")
    title    = _require(raw, "title",    "protocol root")

    # ── Sections that must be present and non-empty ──────────────────────────
    for section in ("inclusion_criteria", "exclusion_criteria", "visit_schedule",
                    "lab_thresholds", "dosing_rules", "reporting_rules"):
        if section not in raw or not isinstance(raw[section], list):
            raise ProtocolLoadError(f"Protocol missing required list section: {section!r}")
        if not raw[section]:
            raise ProtocolLoadError(f"Protocol section {section!r} must not be empty")

    # ── Parse all rule sections ──────────────────────────────────────────────
    all_rules: list[ProtocolRule] = []
    all_rules.extend(_parse_eligibility_rules(raw["inclusion_criteria"], "inclusion"))
    all_rules.extend(_parse_eligibility_rules(raw["exclusion_criteria"], "exclusion"))
    all_rules.extend(_parse_lab_rules(raw["lab_thresholds"]))
    all_rules.extend(_parse_dosing_rules(raw["dosing_rules"]))
    all_rules.extend(_parse_reporting_rules(raw["reporting_rules"]))

    # ── Deduplicate rule IDs ─────────────────────────────────────────────────
    rules_index: dict[str, ProtocolRule] = {}
    for rule in all_rules:
        if rule.rule_id in rules_index:
            raise ProtocolLoadError(
                f"Duplicate rule_id {rule.rule_id!r} found in protocol {trial_id!r}"
            )
        rules_index[rule.rule_id] = rule

    # ── Parse visit schedule ─────────────────────────────────────────────────
    visits = _parse_visit_schedule(raw["visit_schedule"])
    if not visits:
        raise ProtocolLoadError("Protocol visit_schedule must define at least one visit")

    # ── Severity definitions (optional but warn-worthy if missing) ───────────
    severity_defs = raw.get("severity_definitions", {})

    return Protocol(
        trial_id=trial_id,
        version=version,
        title=title,
        visits=visits,
        rules=rules_index,
        severity_definitions=severity_defs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

_cached_protocol: Protocol | None = None


def get_protocol(path: str | Path | None = None) -> Protocol:
    """
    Return the cached Protocol, loading it on first call.

    Parameters
    ----------
    path : str or Path, optional
        If supplied, the cache is bypassed and a fresh Protocol is loaded and
        stored under the new path.  Use this in tests to inject a custom protocol.
    """
    global _cached_protocol
    if path is not None or _cached_protocol is None:
        _cached_protocol = load_protocol(path)
    return _cached_protocol


def reset_protocol_cache() -> None:
    """Clear the cached protocol.  Useful in tests that use custom protocol files."""
    global _cached_protocol
    _cached_protocol = None
