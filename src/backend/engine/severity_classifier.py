"""
Severity classifier for TrialGuard.

Severity is always read from the protocol rule definition (severity_if_violated).
It is NEVER inferred by an AI or heuristic.

This module provides a thin, explicit interface over the protocol so that
the deviation engine does not need to access the full Protocol object just
to classify a rule.
"""
from __future__ import annotations

from src.backend.engine.protocol_loader import (
    VALID_SEVERITIES,
    Protocol,
    ProtocolLoadError,
    get_protocol,
)
from src.backend.models import DeviationSeverity

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class UnknownRuleError(KeyError):
    """Raised when classify() is called with a rule_id not present in the protocol."""


def classify(rule_id: str, protocol: Protocol | None = None) -> DeviationSeverity:
    """
    Return the ``DeviationSeverity`` for the given *rule_id*.

    Parameters
    ----------
    rule_id : str
        The protocol rule identifier, e.g. ``"INC-01"``.
    protocol : Protocol, optional
        Explicit protocol instance.  If omitted the module-level cached
        protocol is used (loaded on first access).

    Returns
    -------
    DeviationSeverity
        One of ``Major``, ``Minor``, ``Administrative``.

    Raises
    ------
    UnknownRuleError
        If *rule_id* is not present in the protocol.
    ProtocolLoadError
        If the severity stored in the protocol is not a recognised value.
        (This is a belt-and-suspenders check; load_protocol already validates
        severity values, so this should never trigger in practice.)
    """
    proto = protocol or get_protocol()

    try:
        severity_str = proto.severity_for(rule_id)
    except KeyError:
        raise UnknownRuleError(
            f"Rule {rule_id!r} is not defined in protocol "
            f"{proto.trial_id!r} v{proto.version}. "
            "Cannot classify severity for an unknown rule."
        )

    # Belt-and-suspenders: validate the stored string maps to our enum
    if severity_str not in VALID_SEVERITIES:
        raise ProtocolLoadError(
            f"Rule {rule_id!r} has an unrecognised severity value "
            f"{severity_str!r} in protocol {proto.trial_id!r}. "
            f"Expected one of {sorted(VALID_SEVERITIES)}."
        )

    return DeviationSeverity(severity_str)


def classify_all(rule_ids: list[str], protocol: Protocol | None = None) -> dict[str, DeviationSeverity]:
    """
    Batch classify a list of rule_ids.

    Returns a dict mapping each rule_id to its DeviationSeverity.
    Raises UnknownRuleError on the first unknown rule_id encountered.
    """
    proto = protocol or get_protocol()
    return {rid: classify(rid, proto) for rid in rule_ids}
