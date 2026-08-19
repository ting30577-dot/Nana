# ADR-007: Explicit ExecutionBackend

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

Every Run freezes its backend and capability limits. `builtin_local` is only
for Nana-owned locked tools and is not a strong sandbox. Unknown code requires
an approved strong backend such as a capability-probed Windows Sandbox or
Docker profile.

## D0 implementation

Run contracts require `backend`, budget, and input snapshot hash. No execution
backend is enabled in D0.

## Gate

Path, network, environment, process-tree, timeout, and budget fixtures must
show zero unblocked violations in the locked corpus before automatic execution.
