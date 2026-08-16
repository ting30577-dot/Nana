import { afterEach, describe, expect, it, vi } from "vitest";
import { browserTransportDependencies, ProjectionStore, type JourneyCommand, type TransportDependencies } from "./store";

const bootstrap = {
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
};

function waitFor(store: ProjectionStore, phase: string): Promise<void> {
  if (store.getSnapshot().phase === phase) return Promise.resolve();
  return new Promise((resolve) => {
    const unsubscribe = store.subscribe(() => {
      if (store.getSnapshot().phase === phase) {
        unsubscribe();
        resolve();
      }
    });
  });
}

function waitForMutation(store: ProjectionStore, phase: string): Promise<void> {
  if (store.getSnapshot().mutation.phase === phase) return Promise.resolve();
  return new Promise((resolve) => {
    const unsubscribe = store.subscribe(() => {
      if (store.getSnapshot().mutation.phase === phase) {
        unsubscribe();
        resolve();
      }
    });
  });
}

const projectCommand: JourneyCommand = {
  type: "CreateProject",
  command_id: "10000000-0000-4000-8000-000000000010",
  expected_revision: 1,
  workspace_id: "10000000-0000-4000-8000-000000000001",
  title: "Mutation transport test",
  data_class: "public",
};

afterEach(() => {
  delete window.__NANA_E2E_TRANSPORT__;
  vi.restoreAllMocks();
});

describe("ProjectionStore", () => {
  it("uses the constructor-time E2E timing override only when present", async () => {
    const delay = vi.fn(async (_milliseconds: number) => undefined);
    const random = vi.fn(() => 0.5);
    window.__NANA_E2E_TRANSPORT__ = { delay, random };
    const dependencies = browserTransportDependencies();
    await dependencies.delay(250);
    expect(delay).toHaveBeenCalledWith(250);
    expect(dependencies.random()).toBe(0.5);
  });

  it("uses real browser dependencies without an override", () => {
    const dependencies = browserTransportDependencies();
    expect(dependencies.fetch).toBeTypeOf("function");
    expect(dependencies.delay).toBeTypeOf("function");
    expect(dependencies.random()).toBeTypeOf("number");
  });

  it("treats an authenticated session rejection as terminal without retry", async () => {
    const fetch = vi.fn(async () => new Response("denied", { status: 401 }));
    const delay = vi.fn(async () => undefined);
    const transport: TransportDependencies = { fetch: fetch as typeof globalThis.fetch, delay, random: () => 0.5 };
    const store = new ProjectionStore(transport);
    store.start();
    await waitFor(store, "session_expired");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(delay).not.toHaveBeenCalled();
    expect(store.getSnapshot().announcement).toContain("会话已过期");
  });

  it("exhausts exactly two bootstrap transport attempts", async () => {
    const fetch = vi.fn(async () => { throw new TypeError("offline"); });
    const delay = vi.fn(async () => undefined);
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay, random: () => 0.5 });
    store.start();
    await waitFor(store, "projection_unavailable");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(delay).toHaveBeenCalledOnce();
    expect(delay).toHaveBeenCalledWith(250);
  });

  it("opens the stream from the bootstrap cursor", async () => {
    const never = new ReadableStream<Uint8Array>({ start() {} });
    const fetch = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) =>
      String(input).endsWith("bootstrap")
        ? Response.json(bootstrap)
        : new Response(never, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await waitFor(store, "live");
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const streamInit = fetch.mock.calls[1][1] as RequestInit;
    expect(new Headers(streamInit.headers).get("Last-Event-ID")).toBe("0");
    store.stop();
  });

  it.each([
    [0, [200, 400, 800, 1600]],
    [0.5, [250, 500, 1000, 2000]],
    [1, [300, 600, 1200, 2000]],
  ])("uses the four capped jittered stream delays for random=%s", async (random, expected) => {
    let request = 0;
    const fetch = vi.fn(async () => {
      request += 1;
      if (request === 1) return Response.json(bootstrap);
      throw new TypeError("offline");
    });
    const delay = vi.fn(async (_milliseconds: number) => undefined);
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay, random: () => random });
    store.start();
    await waitFor(store, "stream_disconnected");
    expect(fetch).toHaveBeenCalledTimes(6);
    expect(delay.mock.calls.map(([milliseconds]) => milliseconds)).toEqual(expected);
  });

  it("manual reconnect creates a fresh single-flight controller at the frozen cursor", async () => {
    let request = 0;
    const fetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      request += 1;
      if (request === 1) return Response.json(bootstrap);
      if (request <= 6) throw new TypeError("offline");
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          init?.signal?.addEventListener("abort", () => controller.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await waitFor(store, "stream_disconnected");
    store.reconnect();
    await waitFor(store, "live");
    expect(fetch).toHaveBeenCalledTimes(7);
    const reconnectInit = fetch.mock.calls[6][1] as RequestInit;
    expect(new Headers(reconnectInit.headers).get("Last-Event-ID")).toBe("0");
    expect(reconnectInit.signal?.aborted).toBe(false);
    store.stop();
  });

  it("refresh rebuilds the canonical snapshot and opens a stream from its new cursor", async () => {
    let bootstrapCount = 0;
    let streamCount = 0;
    const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("bootstrap")) {
        bootstrapCount += 1;
        return Response.json({ ...bootstrap, high_water_event_id: bootstrapCount });
      }
      streamCount += 1;
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          init?.signal?.addEventListener("abort", () => controller.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await waitFor(store, "live");
    store.refresh();
    await vi.waitFor(() => expect(store.getSnapshot().announcement).toBe("正式事件流已连接"));
    expect(bootstrapCount).toBe(2);
    expect(streamCount).toBe(2);
    const secondStream = fetch.mock.calls.at(-1)?.[1] as RequestInit;
    expect(new Headers(secondStream.headers).get("Last-Event-ID")).toBe("2");
    store.stop();
  });

  it("does not refresh a terminal session or projection failure", async () => {
    const fetch = vi.fn(async () => new Response("denied", { status: 401 }));
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await waitFor(store, "session_expired");
    store.refresh();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not reset the one-parser-recovery budget during visibility refresh", async () => {
    let request = 0;
    const fetch = vi.fn(async (_input: RequestInfo | URL) => {
      request += 1;
      if (request === 1) return Response.json(bootstrap);
      if (request === 2) return new Response("id: invalid\ndata: {}\n\n", { status: 200 });
      if (request === 3) return Response.json(bootstrap);
      if (request === 4) return new Response("id: invalid-again\ndata: {}\n\n", { status: 200 });
      return new Response("", { status: 200 });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await waitFor(store, "projection_unavailable");
    expect(fetch).toHaveBeenCalledTimes(4);
    store.refresh();
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it("loads the exact runtime allow-list and attaches bearer authorization", async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer local-test-session");
      return Response.json({
        enabled_mutations: ["CreateProject", "CreateProject", "RequestApproval"],
        external_effects_enabled: true,
        export_selections: [{
          selection_id: "selection_" + "a".repeat(40),
          label: "Dedicated local draft folder",
          expires_at: "2026-08-11T12:00:00Z",
          provenance: "interactive_user",
        }],
      });
    });
    const store = new ProjectionStore({
      fetch: fetch as typeof globalThis.fetch,
      delay: async () => undefined,
      random: () => 0.5,
      authorization: () => "Bearer local-test-session",
    });
    await store.initializeMutations();
    expect(store.getSnapshot().mutation.phase).toBe("idle");
    expect(store.getSnapshot().mutation.enabledCommands).toEqual(["CreateProject", "RequestApproval"]);
    expect(store.getSnapshot().mutation.externalEffectsEnabled).toBe(true);
    expect(store.getSnapshot().mutation.exportSelections).toHaveLength(1);
  });

  it("fails export authority closed for malformed or uncommitted selection summaries", async () => {
    const fetch = vi.fn(async () => Response.json({
      enabled_mutations: ["CreateProject", "RequestApproval"],
      external_effects_enabled: true,
      export_selections: [{ selection_id: "C:\\private\\target", label: "raw path", expires_at: "never", provenance: "interactive_user" }],
    }));
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    await store.initializeMutations();
    expect(store.getSnapshot().mutation).toMatchObject({
      phase: "unavailable",
      enabledCommands: [],
      externalEffectsEnabled: false,
      exportSelections: [],
      errorCode: "E_HANDSHAKE_TRANSPORT",
    });
  });

  it("refreshes canonical receipts after a terminal Action event", async () => {
    let bootstrapCount = 0;
    const terminalEvent = {
      id: 1,
      aggregate_type: "action",
      aggregate_id: "action-export",
      aggregate_version: 1,
      run_id: "run-export",
      run_seq: 1,
      action_id: "action-export",
      type: "action.completed",
      payload: { state: "succeeded", result: "succeeded" },
      occurred_at: "2026-08-11T00:00:01Z",
    };
    const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("bootstrap")) {
        bootstrapCount += 1;
        return Response.json(bootstrapCount === 1 ? bootstrap : {
          ...bootstrap,
          high_water_event_id: 1,
          aggregate_versions: { "action:action-export": 1 },
          run_sequences: { "run-export": 1 },
          activity: [terminalEvent],
          actions: [{ id: "action-export", run_id: "run-export", capability_id: "export.draft_external", state: "succeeded" }],
          receipts: [{ id: "receipt-export", action_id: "action-export", result: "succeeded" }],
          exports: [{ action_id: "action-export", run_id: "run-export", state: "succeeded", approval_id: "approval-export", approval_decision: "approved", write_fenced: 1 }],
        });
      }
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(`id: 1\ndata: ${JSON.stringify(terminalEvent)}\n\n`));
          init?.signal?.addEventListener("abort", () => controller.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    store.start();
    await vi.waitFor(() => expect(store.getSnapshot().projection?.receipts["receipt-export"]).toMatchObject({ result: "succeeded" }));
    expect(bootstrapCount).toBe(2);
    store.stop();
  });

  it("accepts a typed command only after handshake and reconciles from bootstrap", async () => {
    let bootstrapCount = 0;
    const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("handshake")) return Response.json({ enabled_mutations: ["CreateProject"] });
      if (path.endsWith("journey/commands")) {
        expect(init?.method).toBe("POST");
        expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
        expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer transport-test");
        expect(JSON.parse(String(init?.body))).toEqual(projectCommand);
        return Response.json({ command_id: projectCommand.command_id, status: "accepted", affected_revisions: { "project:new": 1 }, event_ids: [1] });
      }
      if (path.endsWith("bootstrap")) {
        bootstrapCount += 1;
        return Response.json({ ...bootstrap, high_water_event_id: bootstrapCount });
      }
      return new Response(new ReadableStream<Uint8Array>({ start() {} }), { status: 200 });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5, authorization: () => "Bearer transport-test" });
    await store.initializeMutations();
    store.start();
    await waitFor(store, "live");
    const result = await store.submitCommand(projectCommand);
    expect(result?.status).toBe("accepted");
    expect(store.getSnapshot().mutation.phase).toBe("reconciled");
    expect(bootstrapCount).toBe(2);
    store.stop();
  });

  it("renders structured conflict context and refreshes canonical facts", async () => {
    let bootstrapCount = 0;
    const fetch = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("handshake")) return Response.json({ enabled_mutations: ["CreateProject"] });
      if (path.endsWith("journey/commands")) return Response.json({ error: { code: "E_REVISION_CONFLICT", message: "Workspace changed", details: { actual_revision: 2 }, data_safe: true } }, { status: 409 });
      if (path.endsWith("bootstrap")) {
        bootstrapCount += 1;
        return Response.json({ ...bootstrap, high_water_event_id: bootstrapCount });
      }
      return new Response(new ReadableStream<Uint8Array>({ start() {} }), { status: 200 });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    await store.initializeMutations();
    store.start();
    await waitFor(store, "live");
    expect(await store.submitCommand(projectCommand)).toBeNull();
    expect(store.getSnapshot().mutation).toMatchObject({ phase: "rejected", errorCode: "E_REVISION_CONFLICT", details: { actual_revision: 2 } });
    expect(bootstrapCount).toBe(2);
    store.stop();
  });

  it("response loss becomes outcome_unknown and retries the exact command id", async () => {
    let commandAttempts = 0;
    const bodies: unknown[] = [];
    const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("handshake")) return Response.json({ enabled_mutations: ["CreateProject"] });
      if (path.endsWith("journey/commands")) {
        commandAttempts += 1;
        bodies.push(JSON.parse(String(init?.body)));
        if (commandAttempts === 1) throw new TypeError("response lost");
        return Response.json({ command_id: projectCommand.command_id, status: "replayed", affected_revisions: { "project:new": 1 }, event_ids: [1] });
      }
      if (path.endsWith("bootstrap")) return Response.json(bootstrap);
      return new Response(new ReadableStream<Uint8Array>({ start() {} }), { status: 200 });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    await store.initializeMutations();
    store.start();
    await waitFor(store, "live");
    expect(await store.submitCommand(projectCommand)).toBeNull();
    expect(store.getSnapshot().mutation.phase).toBe("outcome_unknown");
    expect((await store.retryLastCommand())?.status).toBe("replayed");
    expect(bodies).toEqual([projectCommand, projectCommand]);
    store.stop();
  });

  it("default-denies commands missing from the handshake without a POST", async () => {
    const fetch = vi.fn(async () => Response.json({ enabled_mutations: ["CancelRun"] }));
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    await store.initializeMutations();
    expect(await store.submitCommand(projectCommand)).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(store.getSnapshot().mutation).toMatchObject({ phase: "rejected", errorCode: "E_COMMAND_DISABLED" });
  });

  it("withholds unsafe structured error messages and details", async () => {
    const fetch = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("handshake")) return Response.json({ enabled_mutations: ["CreateProject"] });
      return Response.json({ error: { code: "E_PRIVATE", message: "secret path", details: { path: "private" }, data_safe: false } }, { status: 422 });
    });
    const store = new ProjectionStore({ fetch: fetch as typeof globalThis.fetch, delay: async () => undefined, random: () => 0.5 });
    await store.initializeMutations();
    expect(await store.submitCommand(projectCommand)).toBeNull();
    expect(store.getSnapshot().mutation).toMatchObject({ errorCode: "E_PRIVATE", message: "命令已被驳回；不安全的详情已隐藏", details: null });
  });
});
