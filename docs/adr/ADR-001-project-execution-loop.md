# ADR-001: Project Execution main loop

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

Nana's canonical product loop is:

`goal/inquiry → evidence → editable plan → implementation/run → comparison →
finding/decision → reusable artifact`

Project, Inquiry, Plan, Run, Event, Artifact, Approval, and Receipt form one
control plane shared by later templates.

## Consequences

- UI is organized as Cockpit and Studio journeys, not entity CRUD pages.
- Chat and capability scoring are supporting views, never the canonical loop.
- D0 tests require the control-plane objects in the shared schema.

## Reversal

Changing the main loop is a product-route decision and requires user approval.
