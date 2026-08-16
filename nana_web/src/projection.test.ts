import { describe, expect, it } from "vitest";
import {
  applyProjectionEvent,
  canonicalEventFingerprint,
  projectionFromBootstrap,
  type ProjectionEvent,
} from "./projection";

const bootstrap = () => ({
  high_water_event_id: 0,
  projection_status: "ready",
  aggregate_versions: {},
  run_sequences: {},
  activity: [],
  projects: [],
  inquiries: [],
  plans: [],
  resources: [],
  locators: [],
  claims: [],
  evidence: [],
  hypotheses: [],
  runs: [],
  actions: [],
  artifacts: [],
  findings: [],
  receipts: [],
  approvals: [],
  exports: [],
  needs_you: [],
});

describe("projectionFromBootstrap", () => {
  it.each([
    { projection_status: "invented" },
    { projection_status: "error" },
    { high_water_event_id: Number.MAX_SAFE_INTEGER + 1 },
    { aggregate_versions: { "run:r1": "1" } },
    { run_sequences: { r1: 0 } },
    { actions: [{ state: "running" }] },
    { actions: [{ id: "action-duplicate" }, { id: "action-duplicate" }] },
    { locators: "not-an-array" },
    { activity: [{ id: 0, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 1, run_id: "r1", run_seq: 1, action_id: null, type: "run.started", occurred_at: "2026-08-08T00:00:00Z" }] },
  ])("fails closed for malformed canonical snapshot %#", (override) => {
    expect(() => projectionFromBootstrap({ ...bootstrap(), ...override }))
      .toThrowError(/E_BOOTSTRAP_/);
  });

  it.each([
    {
      high_water_event_id: 5,
      activity: [{ id: 6, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 1, run_id: "r1", run_seq: 1, action_id: null, type: "run.started", occurred_at: "2026-08-08T00:00:01Z" }],
    },
    {
      high_water_event_id: 6,
      activity: [
        { id: 4, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 1, run_id: "r1", run_seq: 1, action_id: null, type: "run.started", occurred_at: "2026-08-08T00:00:01Z" },
        { id: 4, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 2, run_id: "r1", run_seq: 2, action_id: null, type: "run.succeeded", occurred_at: "2026-08-08T00:00:02Z" },
      ],
    },
    {
      high_water_event_id: 6,
      activity: [
        { id: 5, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 1, run_id: "r1", run_seq: 1, action_id: null, type: "run.started", occurred_at: "2026-08-08T00:00:01Z" },
        { id: 3, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 2, run_id: "r1", run_seq: 2, action_id: null, type: "run.succeeded", occurred_at: "2026-08-08T00:00:02Z" },
      ],
    },
    {
      high_water_event_id: 6,
      activity: [{ id: 5, aggregate_type: "run", aggregate_id: "r1", aggregate_version: 1, run_id: null, run_seq: 1, action_id: null, type: "run.started", occurred_at: "2026-08-08T00:00:01Z" }],
    },
  ])("rejects Activity rows outside the bootstrap cursor or in non-increasing order %#", (override) => {
    expect(() => projectionFromBootstrap({ ...bootstrap(), ...override })).toThrowError("E_BOOTSTRAP_ACTIVITY");
  });

  it.each([
    ["workspace", "workspace.created", "ready"],
    ["budget", "budget.created", "degraded"],
    ["relation", "relation.created", "ready"],
    ["budget", "budget.updated", "ready"],
    ["run", "run.future_unknown", "degraded"],
  ])("derives bootstrap projection status for %s Activity", (aggregateType, eventType, expectedStatus) => {
    const activity = {
      id: 1,
      aggregate_type: aggregateType,
      aggregate_id: "aggregate-1",
      aggregate_version: 1,
      run_id: null,
      run_seq: null,
      action_id: null,
      type: eventType,
      occurred_at: "2026-08-08T00:00:01Z",
    };
    const state = projectionFromBootstrap({ ...bootstrap(), high_water_event_id: 1, activity: [activity] });
    expect(state.projection_status).toBe(expectedStatus);
  });

  it.each([
    { id: 0 },
    { aggregate_type: "" },
    { aggregate_version: 0 },
    { run_seq: 0 },
    { run_id: "" },
    { action_id: "" },
    { run_id: null, run_seq: 1 },
    { type: "" },
    { payload: [] },
  ])("fails closed for malformed streamed/replay Event envelopes %#", (override) => {
    const event = {
      id: 10,
      aggregate_type: "run",
      aggregate_id: "run-envelope",
      aggregate_version: 1,
      run_id: "run-envelope",
      run_seq: 1,
      action_id: null,
      type: "run.started",
      payload: { state: "running" },
      occurred_at: "2026-08-08T00:00:10Z",
      ...override,
    } as unknown as ProjectionEvent;
    expect(() => applyProjectionEvent(projectionFromBootstrap(bootstrap()), event))
      .toThrowError("E_EVENT_ENVELOPE");
  });

  it("preserves canonical IDs and relationships for newly streamed facts", () => {
    const events: ProjectionEvent[] = [
      { id: 10, aggregate_type: "run", aggregate_id: "run-new", aggregate_version: 1, run_id: "run-new", run_seq: 1, action_id: null, type: "run.started", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:10Z" },
      { id: 12, aggregate_type: "action", aggregate_id: "action-new", aggregate_version: 1, run_id: "run-new", run_seq: 2, action_id: "action-new", type: "action.started", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:12Z" },
      { id: 19, aggregate_type: "artifact", aggregate_id: "artifact-new", aggregate_version: 1, run_id: "run-new", run_seq: 3, action_id: "action-new", type: "artifact.committed", payload: { state: "available" }, occurred_at: "2026-08-08T00:00:19Z" },
    ];
    const state = events.reduce(applyProjectionEvent, projectionFromBootstrap(bootstrap()));
    expect(state.runs["run-new"]).toMatchObject({ id: "run-new", state: "running" });
    expect(state.actions["action-new"]).toMatchObject({ id: "action-new", run_id: "run-new", state: "running" });
    expect(state.artifacts["artifact-new"]).toMatchObject({ id: "artifact-new", producer_run_id: "run-new", action_id: "action-new", state: "available" });
  });

  it("keeps a future Event type in Activity without inferring domain state", () => {
    const event: ProjectionEvent = {
      id: 11,
      aggregate_type: "run",
      aggregate_id: "run-future",
      aggregate_version: 1,
      run_id: "run-future",
      run_seq: 1,
      action_id: null,
      type: "run.future_unknown",
      payload: { state: "succeeded" },
      occurred_at: "2026-08-08T00:00:11Z",
    };
    const state = applyProjectionEvent(projectionFromBootstrap(bootstrap()), event);
    expect(state.projection_status).toBe("degraded");
    expect(state.activity).toEqual([event]);
    expect(state.runs).toEqual({});
  });

  it("keeps the D2 replay timestamp omission explicit instead of inventing one", () => {
    const replayEvent = {
      id: 10,
      aggregate_type: "run",
      aggregate_id: "run-replay",
      aggregate_version: 1,
      run_id: "run-replay",
      run_seq: 1,
      action_id: null,
      type: "run.started",
      payload: { state: "running" },
    } as ProjectionEvent;
    const state = applyProjectionEvent(projectionFromBootstrap(bootstrap()), replayEvent);
    expect(state.activity[0].occurred_at).toBeUndefined();
    expect(state.runs["run-replay"]).toMatchObject({ id: "run-replay", state: "running" });
  });

  it("projects an Approval lifecycle without inventing authorization", () => {
    const approvalEvent: ProjectionEvent = {
      id: 7,
      aggregate_type: "approval",
      aggregate_id: "approval-pending",
      aggregate_version: 1,
      run_id: "export-run",
      run_seq: 1,
      action_id: "export-action",
      type: "approval.requested",
      payload: { decision: "requested", subject_id: "export-action", subject_hash: `sha256:${"a".repeat(64)}` },
      occurred_at: "2026-08-08T00:00:07Z",
    };
    const state = applyProjectionEvent(projectionFromBootstrap(bootstrap()), approvalEvent);
    expect(state.projection_status).toBe("ready");
    expect(state.activity).toEqual([approvalEvent]);
    expect(state.needs_you).toEqual({});
    expect(state.actions).toEqual({});
    expect(state.approvals["approval-pending"]).toMatchObject({
      id: "approval-pending",
      subject_id: "export-action",
      decision: "requested",
      revision: 1,
    });
  });

  it("normalizes explicit event timestamp offsets for duplicate fingerprints", () => {
    const first: ProjectionEvent = {
      id: 21,
      aggregate_type: "run",
      aggregate_id: "run-time",
      aggregate_version: 1,
      run_id: "run-time",
      run_seq: 1,
      action_id: null,
      type: "run.started",
      payload: { state: "running" },
      occurred_at: "2026-08-08T08:00:00.123400+08:00",
    };
    const equivalent = { ...first, occurred_at: "2026-08-08T00:00:00.1234Z" };
    expect(canonicalEventFingerprint(first)).toBe(canonicalEventFingerprint(equivalent));
    const state = applyProjectionEvent(projectionFromBootstrap(bootstrap()), first);
    expect(applyProjectionEvent(state, equivalent)).toBe(state);
  });

  it("projects streamed Finding facts without degrading the canonical view", () => {
    const finding: ProjectionEvent = {
      id: 31,
      aggregate_type: "finding",
      aggregate_id: "finding-live",
      aggregate_version: 1,
      run_id: "run-terminal",
      run_seq: 1,
      action_id: null,
      type: "finding.drafted",
      payload: {
        finding_id: "finding-live",
        statement: "Observed canonical result",
        status: "draft",
        evidence_ids: ["evidence-1"],
        producer_run_id: "run-terminal",
      },
      occurred_at: "2026-08-08T00:00:31Z",
    };
    const state = applyProjectionEvent(projectionFromBootstrap(bootstrap()), finding);
    expect(state.projection_status).toBe("ready");
    expect(state.findings["finding-live"]).toMatchObject({
      id: "finding-live",
      statement: "Observed canonical result",
      status: "draft",
      evidence_ids: ["evidence-1"],
      producer_run_id: "run-terminal",
    });
  });
});
