# Claude D3-05 repair review packet (sanitized)

Date: 2026-08-08

Scope: independent review of D3-05 repairs only. D3-06 and later are out of
scope. Claude must not edit files.

## Findings repaired

- F-01: prestarted read-only Workspace closes directly on its owner thread.
- F-02: failed second mutation control shuts down its executor.
- F-03: replay binds stored actor and reconstructs the complete rejection.
- F-04: accepted replay binds command-specific aggregate type, event payload,
  and relation/domain rows.
- F-05: public Evidence-to-Claim relations require Evidence status `valid`.
- F-06: descriptor references use the canonical portable-path guard and the
  reader checks final containment; drive, backslash, traversal, and symlink
  tests are present where the platform permits symlink creation.
- F-07: mutation OpenAPI declares structured 409/422/500 ErrorResponse.
- F-08: route inventory compares duplicate route multiplicity.
- F-09: handshake uses canonical schema version/read ceiling constants.
- F-10: configured mutation actor must be a stable user with non-null id.
- F-11: existing bootstrap verifies canonical actor, payload, occurred_at, and
  outbox linkage.

## Evidence added or rerun

- `tests/test_d3_journey_commands.py`: 25 tests, one platform skip; includes
  before/after commit AttachEvidence faults, active-edge replay corruption,
  payload corruption, relation state, resource content drift, and symlink
  rejection.
- `tests/test_d3_journey_runtime.py`: 19 tests; includes different-command
  active-edge race, duplicate security headers, owner close, failed-control
  executor cleanup, HTTP response-loss replay, and committed SSE outbox.
- `tests/test_d3_runtime_authority.py` and `tests/test_d3_read_models.py` pass.
- `python -m compileall nana_sidecar tests scripts` passes.
- D3 related unittest run: 45 tests, one skip, OK (the later full strict set is
  90 tests, two skips, OK, including the Claude adapter fallback test).
- Full unittest run: 353 tests, two skips, OK. The D0 102-entry manifest
  self-check is green, and the D3-05 manifest is synchronized. One
  uncollectable GC warning is printed at interpreter shutdown; the strict D3
  subset under `-W error::ResourceWarning` remains clean.

## Questions for independent adjudication

1. Are F-01 through F-11 sufficiently repaired for implementation closure?
2. Does the payload/domain-row binding adequately close F-04 without a schema
   migration?
3. Are F-13 through F-18 now evidenced enough for D3-05 exit, or are specific
   gaps still open?
4. Is schema v6 still ACCEPT, with any failure of the active-edge race reopening
   a schema-v7 gate?

Return explicit ACCEPT, VETO, or NOT YET CONSENSUS for each question, list
concrete counterexamples if any, and do not infer facts not in this packet.

## Finding-to-evidence matrix for final adjudication

The following is the current exact mapping, so no finding is represented only
by a broad summary:

| Finding | Direct evidence |
|---|---|
| F-01 | `test_prestarted_readonly_workspace_closes_on_its_owner_thread`; strict D3 subset |
| F-02 | `test_second_mutation_control_shuts_down_after_shared_owner_rejection` |
| F-03 | `test_rejected_replay_binds_actor_and_error_fields`; `test_changed_payload_with_same_command_id_fails_closed` |
| F-04 | `test_accepted_replay_rejects_wrong_event_aggregate`; `test_accepted_replay_rejects_tampered_event_payload`; `test_command_log_primary_key_and_begin_immediate_guard_are_present` |
| F-05 | `test_relation_requires_valid_evidence_not_lead`; `test_relation_rejects_every_non_valid_evidence_status` covers every status allowed by the schema CHECK except `valid` |
| F-06 | `test_descriptor_validation_rejects_drive_and_backslash_paths`; `test_resource_content_change_between_register_and_locator_fails_closed`; `test_resource_symlink_is_rejected_when_platform_allows_symlink_creation` (Windows runner lacks symlink privilege and records an explicit skip); D1 reparse/identity tests cover the same OS guard |
| F-07 | `test_checked_in_openapi_is_the_mutation_runtime_authority` asserts structured 409/422/500 refs; `test_http_conflict_returns_structured_error_response`, actor validation assertions, and `test_http_response_loss_after_commit_replays_stored_result` assert actual 409/422/500 JSON bodies |
| F-08 | `test_duplicate_mutation_route_fails_exact_inventory` |
| F-09 | `test_handshake_and_route_inventory_keep_execution_disabled` asserts canonical `SCHEMA_VERSION` and `SCHEMA_READ_CEILING` |
| F-10 | `test_mutation_runtime_rejects_actor_without_stable_id`; `test_user_actor_requires_stable_id` |
| F-11 | `test_bootstrap_corrupted_creation_fact_fails_closed`; `test_workspace_bootstrap_is_exactly_idempotent_and_creates_no_hypothesis` |
| F-12 | `test_bootstrap_failure_closes_sqlite_and_releases_workspace_lock`; `test_second_mutation_control_shuts_down_after_shared_owner_rejection` |
| F-13 | `test_different_command_ids_racing_same_active_edge_are_serialized` repeats twenty fresh-workspace rounds; each round releases eight distinct command IDs through an `asyncio.Barrier`, then applies staggered jitter and asserts all eight reached the barrier, one accepted with one Event, and seven `E_RELATION_INVALID/duplicate_active_relation` conflicts |
| F-14 | `test_multievent_attach_evidence_rolls_back_before_commit_and_replays_after_commit` |
| F-15 | resource drift/symlink tests above plus D1 reparse/identity tests in `test_d3_workspace_lock.py` |
| F-16 | `test_duplicate_security_headers_fail_closed` |
| F-17 | `test_committed_mutation_is_visible_to_sse_outbox_stream`; `test_http_response_loss_after_commit_replays_stored_result` |
| F-18 | `docs/evidence/d3_05_resourcewarning_attribution.md` records the `gc.DEBUG_UNCOLLECTABLE` run: the graph is PySide6/legacy UI metadata; strict D3 subset is clean under `-W error::ResourceWarning` |
| F-19 | `D0EvidenceManifestTests.test_manifest_files_and_digest_match`; D3-05 completion/manifest |

## Schema-v6 non-migration evidence

The repair is implemented entirely against existing schema-v6 tables and
Event types. `test_existing_event_registry_covers_d3_05_without_new_types`
checks the registry; `test_schema_v6_has_no_persisted_workspace_lock_authority`
checks the ownership boundary; and the command-log/`BEGIN IMMEDIATE` test plus
the active-edge race test cover the concurrency invariant. No D3-05 migration
file, ad-hoc table, or new Event type was added. The payload/domain checks are
runtime integrity validation over those existing persisted fields, not a schema
change.

## Review transport note

The packet has received multiple Claude reviews. The latest F-13 confirmation
accepted the barrier-synchronized race structure, but kept D3-06 held because
the packet still contained the earlier HTTP 403 `INSUFFICIENT_BALANCE` history.
This packet now records the twenty-round exact-error evidence and the current
review chronology. A clean final closure request is still required before
claiming joint D3-05 ACCEPT or opening D3-06.
