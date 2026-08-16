import { describe, expect, it } from "vitest";
import { parseSseStream, SseParseError } from "./sse";

function stream(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(input: ReadableStream<Uint8Array>) {
  const values = [];
  for await (const value of parseSseStream(input)) values.push(value);
  return values;
}

const event = JSON.stringify({
  id: 12,
  aggregate_type: "run",
  aggregate_id: "run-1",
  aggregate_version: 1,
  run_id: "run-1",
  run_seq: 1,
  action_id: null,
  type: "run.started",
  payload: { state: "running", note: "line\none" },
  occurred_at: "2026-08-08T00:00:00Z",
  actor: { kind: "system" },
});

describe("parseSseStream", () => {
  it("parses CRLF frames split across UTF-8 chunks", async () => {
    const frame = `id: 12\r\nevent: run.started\r\ndata: ${event}\r\n\r\n`;
    const values = await collect(stream(frame.slice(0, 17), frame.slice(17, 43), frame.slice(43)));
    expect(values).toEqual([{
      id: 12,
      aggregate_type: "run",
      aggregate_id: "run-1",
      aggregate_version: 1,
      run_id: "run-1",
      run_seq: 1,
      action_id: null,
      type: "run.started",
      payload: { state: "running", note: "line\none" },
      occurred_at: "2026-08-08T00:00:00Z",
    }]);
  });

  it("rejects a frame ID that conflicts with the canonical Event", async () => {
    await expect(collect(stream(`id: 13\nevent: run.started\ndata: ${event}\n\n`)))
      .rejects.toMatchObject({ code: "E_SSE_EVENT" });
  });

  it.each([
    ["id", { id: 0 }],
    ["aggregate version", { aggregate_version: 0 }],
    ["empty aggregate type", { aggregate_type: "" }],
    ["empty aggregate identity", { aggregate_id: "" }],
    ["run sequence", { run_seq: 0 }],
    ["empty run identity", { run_id: "" }],
    ["empty action identity", { action_id: "" }],
    ["empty occurrence timestamp", { occurred_at: "" }],
    ["orphan run sequence", { run_id: null, run_seq: 1 }],
  ])("rejects malformed %s", async (_label, override) => {
    const invalid = JSON.stringify({ ...JSON.parse(event), ...override });
    const id = String((JSON.parse(invalid) as { id: number }).id);
    await expect(collect(stream(`id: ${id}\nevent: run.started\ndata: ${invalid}\n\n`)))
      .rejects.toMatchObject({ code: "E_SSE_EVENT" });
  });

  it("fails closed for an SQLite-range Event ID beyond JavaScript safe integers", async () => {
    const unsafeId = 9007199254740992;
    const invalid = JSON.stringify({ ...JSON.parse(event), id: unsafeId });
    await expect(collect(stream(`id: ${unsafeId}\nevent: run.started\ndata: ${invalid}\n\n`)))
      .rejects.toMatchObject({ code: "E_SSE_EVENT" });
  });

  it("joins multiple data fields with a newline before parsing JSON", async () => {
    const split = event.indexOf('"aggregate_type"');
    const frame = `id: 12\nevent: run.started\ndata: ${event.slice(0, split)}\ndata: ${event.slice(split)}\n\n`;
    const values = await collect(stream(frame));
    expect(values).toHaveLength(1);
    expect(values[0]).toMatchObject({ id: 12, type: "run.started", aggregate_id: "run-1" });
  });

  it("rejects a truncated final frame without cursor output", async () => {
    await expect(collect(stream(`id: 12\nevent: run.started\ndata: ${event}`)))
      .rejects.toMatchObject({ code: "E_SSE_TRUNCATED" });
  });
});
