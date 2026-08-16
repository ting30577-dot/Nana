# D3-07 runtime surface audit (no-edit scan)

Date: 2026-08-09  
Scope: verify that pre-gate D3 runtime does not accidentally expose Approval or
external-export mutation despite generic D2 contract schemas being present.

## Findings before any repair

| ID | Severity | Finding | Evidence | Decision |
|---|---|---|---|---|
| F07-11 | P1 | The generated OpenAPI component catalog contains generic `RequestApproval`, `DecideApproval`, and `PublishExport` schemas. | These are D2/domain contract definitions, while the journey route discriminator is a separate 13-variant `JourneyCommandRequest`. | Open; requires explicit negative-surface evidence. |
| F07-12 | P0 | No runtime route may bind the generic Approval/export schemas before the joint 07-00 gate. | The only mutable route is `/api/v1/journey/commands`; its route mapping must remain exactly the curated D3-05/D3-06 union. | VETO any route expansion. |
| F07-13 | P1 | The handshake must distinguish enabled T2 journey mutations from external effects. | A browser needs to know that execution is enabled for the locked fixture while external filesystem effects remain disabled. | Open; verify handshake evidence. |

## Evidence review

- `tests/test_d3_journey_runtime.py::test_checked_in_openapi_is_the_mutation_runtime_authority`
  asserts the checked-in OpenAPI equals the runtime schema, the route has exactly
  13 curated variants, and no generic actor field is browser-supplied.
- The same test asserts the exact mutation route inventory and the presence of
  `StartRun`/`CancelRun`; generic Approval/export command names are not in the
  route discriminator mapping.
- `JourneyCommandRequest` and `JOURNEY_COMMAND_NAMES` contain no
  `RequestApproval`, `DecideApproval`, `AuthorizeAction`, `PublishExport`, or
  PolicyGrant variant.
- `JourneyCommandService._apply` has no Approval, authorization, or export
  handler; `PublishExport` is not executable through the route.
- The handshake test asserts `external_effects_enabled == false` while the
  curated locked T2 journey is enabled.

## Second no-edit scan verdict

F07-11 is ACCEPTED as a documented negative boundary: generic schemas remain
read-only contract catalog material and are not route-authorized. F07-12 is
VETOED for any expansion and is currently satisfied by the exact route-inventory
test. F07-13 is ACCEPTED for the current pre-T3 runtime. No code edit was needed;
the existing tests are the regression evidence. Any D3-07 route addition still
requires the unresolved joint gate and a new security review.

