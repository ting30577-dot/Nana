import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "../nana_web/node_modules/typescript/lib/typescript.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(root, "nana_web/src/projection.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const output = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const module = { exports: {} };
vm.runInNewContext(output, {
  module,
  exports: module.exports,
  TextEncoder,
  Uint8Array,
  DataView,
  BigInt,
});
const projection = module.exports;
if (projection.sha256("abc") !== "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
  throw new Error("SHA-256 self-test failed");
}

const state = () => ({
  high_water_event_id: 0,
  projection_status: "ready",
  aggregate_versions: {},
  run_sequences: {},
  activity: [],
  runs: {}, actions: {}, artifacts: {}, findings: {}, receipts: {}, needs_you: {}, fingerprints: {},
});
const event = (id, version, overrides = {}) => ({
  id, aggregate_type: "action", aggregate_id: "a1", aggregate_version: version,
  run_id: "r1", run_seq: version, action_id: "a1", type: "action.started",
  payload: { action_id: "a1", state: "running" }, occurred_at: "2026-08-01T00:00:00Z", ...overrides,
});
let current = projection.applyProjectionEvent(state(), event(10, 1));
current = projection.applyProjectionEvent(current, event(12, 2));
if (current.high_water_event_id !== 12) throw new Error("sparse ID failed");
if (projection.applyProjectionEvent(current, event(12, 2)) !== current) throw new Error("duplicate replay failed");
for (const [candidate, code] of [[event(12, 2, { payload: { changed: true } }), "E_EVENT_ID_CONFLICT"], [event(11, 3), "E_EVENT_ID_DECREASING"], [event(13, 4, { run_seq: 4 }), "E_AGGREGATE_SEQUENCE"]]) {
  try { projection.applyProjectionEvent(current, candidate); throw new Error(`${code} was not rejected`); }
  catch (error) { if (error.code !== code) throw error; }
}
const unknown = projection.applyProjectionEvent(current, event(19, 1, { aggregate_type: "budget", aggregate_id: "r1", action_id: null, run_seq: 3, type: "future.unknown" }));
if (unknown.projection_status !== "degraded") throw new Error("unknown event did not degrade projection");
const handoff = JSON.parse(fs.readFileSync(path.join(root, "fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json"), "utf8"));
const replayed = projection.projectionFromD2Handoff(handoff);
if (replayed.high_water_event_id !== 9 || replayed.actions[handoff.actions[0].id].state !== "succeeded") {
  throw new Error("D2 handoff adapter failed");
}
console.log("projection self-test: pass");
