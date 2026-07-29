"""Authoritative state-transition registry from architecture section 6.1."""

from __future__ import annotations

from collections.abc import Mapping


TRANSITIONS: Mapping[str, Mapping[str, frozenset[str]]] = {
    "resource": {
        "draft": frozenset({"available", "failed", "tombstoned"}),
        "available": frozenset({"stale", "tombstoned"}),
        "stale": frozenset({"available", "tombstoned"}),
        "failed": frozenset({"draft", "tombstoned"}),
        "tombstoned": frozenset(),
    },
    "locator": {
        "draft": frozenset({"valid", "invalid", "tombstoned"}),
        "valid": frozenset({"stale", "source_unavailable", "tombstoned"}),
        "stale": frozenset({"valid", "tombstoned"}),
        "source_unavailable": frozenset({"valid", "tombstoned"}),
        "invalid": frozenset({"draft", "tombstoned"}),
        "tombstoned": frozenset(),
    },
    "claim": {
        "draft": frozenset({"in_review", "superseded"}),
        "in_review": frozenset({"verified", "contested", "rejected", "draft"}),
        "verified": frozenset({"in_review", "superseded"}),
        "contested": frozenset({"in_review", "superseded"}),
        "rejected": frozenset({"in_review", "superseded"}),
        "superseded": frozenset(),
    },
    "evidence": {
        "lead": frozenset({"valid", "rejected", "tombstoned"}),
        "valid": frozenset({"stale", "source_unavailable", "tombstoned"}),
        "stale": frozenset({"valid", "tombstoned"}),
        "source_unavailable": frozenset({"valid", "tombstoned"}),
        "rejected": frozenset({"lead", "tombstoned"}),
        "tombstoned": frozenset(),
    },
    "hypothesis": {
        "proposed": frozenset({"testing", "superseded"}),
        "testing": frozenset({"supported", "falsified", "inconclusive"}),
        "supported": frozenset({"testing", "superseded"}),
        "falsified": frozenset({"testing", "superseded"}),
        "inconclusive": frozenset({"testing", "superseded"}),
        "superseded": frozenset(),
    },
    "method": {
        "draft": frozenset({"validated", "deprecated", "superseded"}),
        "validated": frozenset({"deprecated", "superseded"}),
        "deprecated": frozenset({"validated", "superseded"}),
        "superseded": frozenset(),
    },
    "finding": {
        "draft": frozenset({"in_review", "superseded"}),
        "in_review": frozenset({"accepted", "rejected", "draft"}),
        "accepted": frozenset({"in_review", "superseded"}),
        "rejected": frozenset({"in_review", "superseded"}),
        "superseded": frozenset(),
    },
    "decision": {
        "draft": frozenset({"in_review", "rejected", "superseded"}),
        "in_review": frozenset({"confirmed", "rejected", "draft"}),
        "confirmed": frozenset({"superseded"}),
        "rejected": frozenset({"draft", "superseded"}),
        "superseded": frozenset(),
    },
    "project": {
        "active": frozenset({"paused", "archived"}),
        "paused": frozenset({"active", "archived"}),
        "archived": frozenset(),
    },
    "inquiry": {
        "draft": frozenset({"ready", "cancelled"}),
        "ready": frozenset({"active", "cancelled"}),
        "active": frozenset({"blocked", "in_review", "cancelled"}),
        "blocked": frozenset({"active", "cancelled"}),
        "in_review": frozenset({"active", "decided", "closed"}),
        "decided": frozenset({"active", "closed"}),
        "cancelled": frozenset(),
        "closed": frozenset(),
    },
    "plan": {
        "draft": frozenset({"proposed", "superseded"}),
        "proposed": frozenset({"approved", "rejected", "draft"}),
        "approved": frozenset({"running", "superseded"}),
        "running": frozenset({"completed", "superseded"}),
        "completed": frozenset(),
        "rejected": frozenset(),
        "superseded": frozenset(),
    },
    "artifact": {
        "staged": frozenset({"available", "failed", "orphan_quarantined"}),
        "available": frozenset({"corrupt", "tombstoned"}),
        "corrupt": frozenset({"available", "tombstoned"}),
        "failed": frozenset({"available", "garbage_collected"}),
        "orphan_quarantined": frozenset({"available", "garbage_collected"}),
        "tombstoned": frozenset(),
        "garbage_collected": frozenset(),
    },
    "policy_grant": {
        "proposed": frozenset({"active", "rejected"}),
        "active": frozenset({"revoked", "expired", "exhausted"}),
        "rejected": frozenset(),
        "revoked": frozenset(),
        "expired": frozenset(),
        "exhausted": frozenset(),
    },
    "approval": {
        "requested": frozenset({"approved", "denied", "expired"}),
        "approved": frozenset(),
        "denied": frozenset(),
        "expired": frozenset(),
    },
    "run": {
        "proposed": frozenset({"queued"}),
        "queued": frozenset({"running", "cancelled"}),
        "running": frozenset(
            {
                "paused",
                "succeeded",
                "failed",
                "cancelled",
                "timed_out",
                "budget_exceeded",
                "orphaned",
            }
        ),
        "paused": frozenset({"queued", "cancelled", "timed_out"}),
        "succeeded": frozenset(),
        "failed": frozenset(),
        "cancelled": frozenset(),
        "timed_out": frozenset(),
        "budget_exceeded": frozenset(),
        "orphaned": frozenset(),
    },
    "action": {
        "proposed": frozenset({"waiting_approval", "authorized", "denied"}),
        "waiting_approval": frozenset({"authorized", "denied", "expired"}),
        "authorized": frozenset({"running", "cancelled"}),
        "running": frozenset(
            {"succeeded", "failed", "cancelled", "timed_out", "effect_unknown"}
        ),
        "succeeded": frozenset(),
        "failed": frozenset(),
        "cancelled": frozenset(),
        "timed_out": frozenset(),
        "denied": frozenset(),
        "expired": frozenset(),
        "effect_unknown": frozenset(),
    },
    "relation": {
        "active": frozenset({"tombstoned"}),
        "tombstoned": frozenset(),
    },
}


INITIAL_STATES: Mapping[str, str] = {
    "resource": "draft",
    "locator": "draft",
    "claim": "draft",
    "evidence": "lead",
    "hypothesis": "proposed",
    "method": "draft",
    "finding": "draft",
    "decision": "draft",
    "project": "active",
    "inquiry": "draft",
    "plan": "draft",
    "artifact": "staged",
    "policy_grant": "proposed",
    "approval": "requested",
    "run": "proposed",
    "action": "proposed",
    "relation": "active",
}


TERMINAL_STATES: Mapping[str, frozenset[str]] = {
    object_type: frozenset(
        state for state, targets in transitions.items() if not targets
    )
    for object_type, transitions in TRANSITIONS.items()
}


class StateTransitionError(ValueError):
    code = "E_STATE_TRANSITION"

    def __init__(
        self,
        object_type: str,
        object_id: str,
        current: str,
        target: str,
        expected_revision: int,
    ) -> None:
        self.details = {
            "object_type": object_type,
            "id": object_id,
            "from": current,
            "to": target,
            "expected_revision": expected_revision,
        }
        super().__init__(
            f"{self.code}({object_type}, {object_id}, {current}, "
            f"{target}, {expected_revision})"
        )


def assert_transition(
    object_type: str,
    object_id: str,
    current: str,
    target: str,
    expected_revision: int,
) -> None:
    """Raise a structured error unless the registry permits the transition."""

    allowed = TRANSITIONS.get(object_type, {}).get(current, frozenset())
    if target not in allowed:
        raise StateTransitionError(
            object_type, object_id, current, target, expected_revision
        )
