# ADR-005: Closed Capability Registry

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

Agents can invoke only registered capabilities with a version, executable
digest, argument schema, directory/network/environment policy, resource
limits, risk tier, and Receipt rule. Arbitrary shell strings are not a
capability.

## First dev capability

`python.unittest.locked` will allow exactly the frozen test identifiers defined
by the fixture, with network denied and writes restricted to project scratch.
It is implemented in D2 after scheduler/cancel foundations.

## Gate

Unknown capability or out-of-policy arguments must be rejected before process
start.
