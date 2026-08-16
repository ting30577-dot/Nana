/** Canonical sparse-event projection shared by browser SSE and offline replay. */

// Bootstrap/reducer states are canonical read-model states. Transport or
// reducer failure is represented by the store's terminal
// `projection_unavailable` phase, never by a partially usable projection.
export type ProjectionStatus = "ready" | "degraded";

export interface ProjectionEvent {
  id: number;
  aggregate_type: string;
  aggregate_id: string;
  aggregate_version: number;
  run_id: string | null;
  run_seq: number | null;
  action_id: string | null;
  type: string;
  payload: Record<string, unknown> | null;
  /** Live SSE frames carry this field; the frozen D2 replay fixture omits it. */
  occurred_at?: string;
}

export type ProjectionActivity = Omit<ProjectionEvent, "payload"> & {
  payload?: Record<string, unknown> | null;
};

export interface ProjectionState {
  high_water_event_id: number;
  projection_status: ProjectionStatus;
  aggregate_versions: Record<string, number>;
  run_sequences: Record<string, number>;
  activity: ProjectionActivity[];
  runs: Record<string, Record<string, unknown>>;
  actions: Record<string, Record<string, unknown>>;
  artifacts: Record<string, Record<string, unknown>>;
  hypotheses: Record<string, Record<string, unknown>>;
  findings: Record<string, Record<string, unknown>>;
  receipts: Record<string, Record<string, unknown>>;
  approvals: Record<string, Record<string, unknown>>;
  exports: Record<string, Record<string, unknown>>;
  needs_you: Record<string, Record<string, unknown>>;
  fingerprints: Record<number, string>;
}

export class ProjectionError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
}

function nullableIdentifier(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && value !== "");
}

/** Validate the canonical Event envelope shared by SSE and replay adapters. */
function assertProjectionEvent(value: unknown): asserts value is ProjectionEvent {
  if (!isRecord(value)) throw new ProjectionError("E_EVENT_ENVELOPE");
  if (
    !positiveInteger(value.id)
    || typeof value.aggregate_type !== "string"
    || value.aggregate_type === ""
    || typeof value.aggregate_id !== "string"
    || value.aggregate_id === ""
    || !positiveInteger(value.aggregate_version)
    || !nullableIdentifier(value.run_id)
    || !(value.run_seq === null || (value.run_id !== null && positiveInteger(value.run_seq)))
    || !nullableIdentifier(value.action_id)
    || typeof value.type !== "string"
    || value.type === ""
    || !(value.occurred_at === undefined || typeof value.occurred_at === "string")
    || !(value.payload === null || (isRecord(value.payload)))
  ) {
    throw new ProjectionError("E_EVENT_ENVELOPE");
  }
}

type BootstrapMap = Record<string, unknown>[];

const COLLECTIONS = [
  "projects", "inquiries", "plans", "resources", "locators", "claims", "evidence", "hypotheses",
  "runs", "actions", "artifacts", "findings", "receipts", "approvals", "exports", "needs_you",
] as const;

// Bootstrap collections already carry the canonical state for these
// aggregate/event pairs. A known aggregate with a future event type is still
// unknown to this reducer: keep it in Activity and require an upgrade banner.
const BOOTSTRAP_KNOWN_EVENT_KEYS = new Set([
  "workspace:workspace.created",
  "project:project.created", "project:project.status_changed",
  "inquiry:inquiry.created", "inquiry:inquiry.status_changed",
  "plan:plan.proposed", "plan:plan.revised", "plan:plan.status_changed",
  "resource:resource.registered", "locator:locator.created", "claim:claim.created",
  "evidence:evidence.attached", "hypothesis:hypothesis.created", "finding:finding.drafted",
  "run:run.created", "run:run.started", "run:run.heartbeat", "run:run.paused",
  "run:run.cancelled", "run:run.timed_out", "run:run.failed", "run:run.succeeded",
  "run:run.budget_exceeded", "run:run.orphaned",
  "action:action.proposed", "action:action.authorized", "action:action.started",
  "action:action.output", "action:action.completed", "action:action.cancelled",
  "action:action.effect_unknown",
  "approval:approval.requested", "approval:approval.decided", "approval:approval.expired",
  "budget:budget.updated", "budget:budget.threshold_reached",
  "relation:relation.created",
  "artifact:artifact.staged", "artifact:artifact.committed", "artifact:artifact.reconciled",
]);

const REDUCER_EVENT_KEYS = new Set([
  "run:run.created", "run:run.started", "run:run.heartbeat", "run:run.paused",
  "run:run.cancelled", "run:run.timed_out", "run:run.failed", "run:run.succeeded",
  "run:run.budget_exceeded", "run:run.orphaned",
  "action:action.proposed", "action:action.authorized", "action:action.started",
  "action:action.output", "action:action.completed", "action:action.cancelled",
  "action:action.effect_unknown",
  "approval:approval.requested", "approval:approval.decided", "approval:approval.expired",
  "artifact:artifact.staged", "artifact:artifact.committed", "artifact:artifact.reconciled",
  "hypothesis:hypothesis.created", "finding:finding.drafted",
]);

function objectRows(snapshot: Record<string, unknown>, name: string): BootstrapMap {
  const value = snapshot[name];
  if (!Array.isArray(value) || value.some((row) => row === null || typeof row !== "object" || Array.isArray(row))) {
    throw new ProjectionError("E_BOOTSTRAP_COLLECTION");
  }
  return value as BootstrapMap;
}

function positiveWatermarks(value: unknown): Record<string, number> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ProjectionError("E_BOOTSTRAP_WATERMARKS");
  }
  const entries = Object.entries(value);
  if (entries.some(([key, watermark]) => key === "" || typeof watermark !== "number" || !Number.isSafeInteger(watermark) || watermark < 1)) {
    throw new ProjectionError("E_BOOTSTRAP_WATERMARKS");
  }
  return Object.fromEntries(entries);
}

function activityRows(snapshot: Record<string, unknown>, highWater: number): ProjectionActivity[] {
  const rows = objectRows(snapshot, "activity");
  const positiveInteger = (value: unknown): value is number =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
  if (rows.some((row) =>
    !positiveInteger(row.id)
    || typeof row.aggregate_type !== "string"
    || typeof row.aggregate_id !== "string"
    || !positiveInteger(row.aggregate_version)
    || !nullableIdentifier(row.run_id)
    || !(row.run_seq === null || (row.run_id !== null && positiveInteger(row.run_seq)))
    || !nullableIdentifier(row.action_id)
    || typeof row.type !== "string"
    || typeof row.occurred_at !== "string"
  )) {
    throw new ProjectionError("E_BOOTSTRAP_ACTIVITY");
  }
  let previousId = 0;
  for (const row of rows) {
    const id = row.id as number;
    if (id <= previousId || id > highWater) throw new ProjectionError("E_BOOTSTRAP_ACTIVITY");
    previousId = id;
  }
  return rows as ProjectionActivity[];
}

function recordsById(rows: BootstrapMap, id = "id"): Record<string, Record<string, unknown>> {
  const identifiers = rows.map((row) => row[id]);
  if (identifiers.some((value) => typeof value !== "string" || value === "")) {
    throw new ProjectionError("E_BOOTSTRAP_ID");
  }
  if (new Set(identifiers as string[]).size !== identifiers.length) {
    throw new ProjectionError("E_BOOTSTRAP_ID");
  }
  return Object.fromEntries(rows.map((row) => [row[id] as string, row]));
}

export function projectionFromBootstrap(snapshot: Record<string, unknown>): ProjectionState {
  const highWater = snapshot.high_water_event_id;
  if (typeof highWater !== "number" || !Number.isSafeInteger(highWater) || highWater < 0) {
    throw new ProjectionError("E_BOOTSTRAP_CURSOR");
  }
  if (snapshot.projection_status !== "ready" && snapshot.projection_status !== "degraded") {
    throw new ProjectionError("E_BOOTSTRAP_STATUS");
  }
  const rows = Object.fromEntries(COLLECTIONS.map((name) => [name, objectRows(snapshot, name)])) as Record<(typeof COLLECTIONS)[number], BootstrapMap>;
  const activity = activityRows(snapshot, highWater);
  const activityNeedsUpgrade = activity.some((event) =>
    !BOOTSTRAP_KNOWN_EVENT_KEYS.has(`${event.aggregate_type}:${event.type}`));
  return {
    high_water_event_id: highWater,
    projection_status: snapshot.projection_status === "degraded" || activityNeedsUpgrade ? "degraded" : "ready",
    aggregate_versions: positiveWatermarks(snapshot.aggregate_versions),
    run_sequences: positiveWatermarks(snapshot.run_sequences),
    activity,
    runs: recordsById(rows.runs),
    actions: recordsById(rows.actions),
    artifacts: recordsById(rows.artifacts),
    hypotheses: recordsById(rows.hypotheses),
    findings: recordsById(rows.findings),
    receipts: recordsById(rows.receipts),
    approvals: recordsById(rows.approvals),
    exports: recordsById(rows.exports, "action_id"),
    needs_you: recordsById(rows.needs_you, "action_id"),
    fingerprints: {},
  };
}

/** Adapter only: D2 handoff is data for the same reducer, never a second HTTP contract. */
export function projectionFromD2Handoff(fixture: Record<string, unknown>): ProjectionState {
  const state = projectionFromBootstrap({
    high_water_event_id: 0,
    projection_status: "ready",
    aggregate_versions: {},
    run_sequences: {},
    activity: [],
    projects: [], inquiries: [], plans: [], resources: [], locators: [], claims: [], evidence: [], hypotheses: [],
    runs: fixture.run ? [fixture.run] : [],
    actions: fixture.actions ?? [],
    artifacts: [], findings: [], receipts: fixture.receipts ?? [], approvals: [], exports: [], needs_you: [],
  });
  const events = fixture.events;
  if (!Array.isArray(events)) throw new ProjectionError("E_HANDOFF_EVENTS");
  return events.reduce((current, raw) => applyProjectionEvent(current, raw as ProjectionEvent), state);
}

function stableJson(value: unknown): string {
  if (value === undefined) return "null";
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object)
    .sort()
    .filter((key) => object[key] !== undefined)
    .map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`)
    .join(",")}}`;
}

/**
 * Event timestamps are canonicalized before fingerprinting.  Only explicit
 * ISO-8601 timestamps with a timezone are normalized; malformed or timezone-
 * naive strings remain unchanged so they cannot be silently repaired.
 */
function normalizeUtcTimestamp(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(value);
  if (!match) {
    return value;
  }
  const [, localDateTime, fraction = "", zone, sign, offsetHours, offsetMinutes] = match;
  const parsed = new Date(`${localDateTime}Z`);
  if (
    Number.isNaN(parsed.getTime())
    || parsed.toISOString().slice(0, 19) !== localDateTime
    || (zone !== "Z" && (Number(offsetHours) > 23 || Number(offsetMinutes) > 59))
  ) return value;
  const offset = zone === "Z"
    ? 0
    : (Number(offsetHours) * 60 + Number(offsetMinutes)) * (sign === "+" ? 1 : -1);
  const utc = new Date(parsed.getTime() - offset * 60_000).toISOString().slice(0, 19);
  const canonicalFraction = fraction.replace(/0+$/, "");
  return `${utc}${canonicalFraction ? `.${canonicalFraction}` : ""}Z`;
}

const SHA256_INITIAL = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];
const SHA256_CONSTANTS = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

function rotateRight(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits));
}

/** Small synchronous SHA-256 implementation so the pure reducer stays synchronous. */
export function sha256(value: string): string {
  const input = new TextEncoder().encode(value);
  const bitLength = BigInt(input.length) * 8n;
  const paddedLength = Math.ceil((input.length + 1 + 8) / 64) * 64;
  const bytes = new Uint8Array(paddedLength);
  bytes.set(input);
  bytes[input.length] = 0x80;
  const view = new DataView(bytes.buffer);
  view.setUint32(paddedLength - 8, Number((bitLength >> 32n) & 0xffffffffn));
  view.setUint32(paddedLength - 4, Number(bitLength & 0xffffffffn));
  const hash = [...SHA256_INITIAL];
  const words = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) words[index] = view.getUint32(offset + index * 4);
    for (let index = 16; index < 64; index += 1) {
      const s0 = rotateRight(words[index - 15], 7) ^ rotateRight(words[index - 15], 18) ^ (words[index - 15] >>> 3);
      const s1 = rotateRight(words[index - 2], 17) ^ rotateRight(words[index - 2], 19) ^ (words[index - 2] >>> 10);
      words[index] = (words[index - 16] + s0 + words[index - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const s1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + s1 + choice + SHA256_CONSTANTS[index] + words[index]) >>> 0;
      const s0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + majority) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0; d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    hash[0] = (hash[0] + a) >>> 0; hash[1] = (hash[1] + b) >>> 0;
    hash[2] = (hash[2] + c) >>> 0; hash[3] = (hash[3] + d) >>> 0;
    hash[4] = (hash[4] + e) >>> 0; hash[5] = (hash[5] + f) >>> 0;
    hash[6] = (hash[6] + g) >>> 0; hash[7] = (hash[7] + h) >>> 0;
  }
  return hash.map((word) => word.toString(16).padStart(8, "0")).join("");
}

export function canonicalEventFingerprint(event: ProjectionEvent): string {
  return sha256(stableJson({ ...event, occurred_at: normalizeUtcTimestamp(event.occurred_at) }));
}

function aggregateKey(event: ProjectionEvent): string {
  return `${event.aggregate_type}:${event.aggregate_id}`;
}

function cloneState(state: ProjectionState): ProjectionState {
  return {
    ...state,
    aggregate_versions: { ...state.aggregate_versions },
    run_sequences: { ...state.run_sequences },
    activity: [...state.activity],
    runs: { ...state.runs },
    actions: { ...state.actions },
    artifacts: { ...state.artifacts },
    hypotheses: { ...state.hypotheses },
    findings: { ...state.findings },
    receipts: { ...state.receipts },
    approvals: { ...state.approvals },
    exports: { ...state.exports },
    needs_you: { ...state.needs_you },
    fingerprints: { ...state.fingerprints },
  };
}

function patchDomain(state: ProjectionState, event: ProjectionEvent): void {
  const payload = event.payload ?? {};
  if (event.aggregate_type === "run" && event.run_id) {
    state.runs[event.run_id] = {
      id: event.run_id,
      ...(state.runs[event.run_id] ?? {}),
      state: payload.state ?? event.type,
    };
  } else if (event.aggregate_type === "action" && event.action_id) {
    state.actions[event.action_id] = {
      id: event.action_id,
      run_id: event.run_id,
      ...(state.actions[event.action_id] ?? {}),
      state: payload.state ?? payload.result ?? event.type,
    };
    if (payload.state === "waiting_approval") state.needs_you[event.action_id] = { action_id: event.action_id, state: "waiting_approval" };
    else delete state.needs_you[event.action_id];
  } else if (event.aggregate_type === "artifact") {
    state.artifacts[event.aggregate_id] = {
      id: event.aggregate_id,
      producer_run_id: event.run_id,
      action_id: event.action_id,
      ...(state.artifacts[event.aggregate_id] ?? {}),
      state: payload.state ?? event.type,
    };
  } else if (event.aggregate_type === "hypothesis") {
    state.hypotheses[event.aggregate_id] = {
      id: event.aggregate_id,
      ...(state.hypotheses[event.aggregate_id] ?? {}),
      ...payload,
      status: payload.status ?? event.type,
    };
  } else if (event.aggregate_type === "finding") {
    state.findings[event.aggregate_id] = {
      id: event.aggregate_id,
      producer_run_id: event.run_id,
      ...(state.findings[event.aggregate_id] ?? {}),
      ...payload,
      status: payload.status ?? event.type,
    };
  } else if (event.aggregate_type === "approval") {
    state.approvals[event.aggregate_id] = {
      id: event.aggregate_id,
      ...(state.approvals[event.aggregate_id] ?? {}),
      ...payload,
      decision: payload.decision ?? (event.type === "approval.expired" ? "expired" : "requested"),
      revision: event.aggregate_version,
    };
  }
}

export function applyProjectionEvent(state: ProjectionState, event: ProjectionEvent): ProjectionState {
  assertProjectionEvent(event);
  const fingerprint = canonicalEventFingerprint(event);
  const priorFingerprint = state.fingerprints[event.id];
  if (priorFingerprint !== undefined) {
    if (priorFingerprint === fingerprint) return state;
    throw new ProjectionError("E_EVENT_ID_CONFLICT");
  }
  if (event.id <= state.high_water_event_id) throw new ProjectionError("E_EVENT_ID_DECREASING");
  const aggregate = aggregateKey(event);
  const expectedAggregate = (state.aggregate_versions[aggregate] ?? 0) + 1;
  if (event.aggregate_version !== expectedAggregate) throw new ProjectionError("E_AGGREGATE_SEQUENCE");
  if (event.run_id !== null && event.run_seq !== null) {
    const expectedRun = (state.run_sequences[event.run_id] ?? 0) + 1;
    if (event.run_seq !== expectedRun) throw new ProjectionError("E_RUN_SEQUENCE");
  }
  const next = cloneState(state);
  next.fingerprints[event.id] = fingerprint;
  next.high_water_event_id = event.id;
  next.aggregate_versions[aggregate] = event.aggregate_version;
  if (event.run_id !== null && event.run_seq !== null) next.run_sequences[event.run_id] = event.run_seq;
  next.activity.push(event);
  if (next.activity.length > 200) next.activity.shift();
  const eventKey = `${event.aggregate_type}:${event.type}`;
  if (REDUCER_EVENT_KEYS.has(eventKey)) patchDomain(next, event);
  else if (!BOOTSTRAP_KNOWN_EVENT_KEYS.has(eventKey)) next.projection_status = "degraded";
  return next;
}
