import type { ProjectionEvent } from "./projection";

const MAX_SQLITE_ID = 9_223_372_036_854_775_807n;

export class SseParseError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

function boundary(buffer: string): { index: number; length: number } | null {
  const matches = ["\r\n\r\n", "\n\n", "\r\r"]
    .map((separator) => ({ index: buffer.indexOf(separator), length: separator.length }))
    .filter((match) => match.index >= 0)
    .sort((left, right) => left.index - right.index);
  return matches[0] ?? null;
}

function eventFromFrame(frame: string): ProjectionEvent | null {
  let idText: string | null = null;
  let eventType: string | null = null;
  const data: string[] = [];
  for (const line of frame.split(/\r\n|\n|\r/)) {
    if (line === "" || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id") idText = value;
    else if (field === "event") eventType = value;
    else if (field === "data") data.push(value);
  }
  if (idText === null && eventType === null && data.length === 0) return null;
  if (idText === null || !/^\d+$/.test(idText) || BigInt(idText) > MAX_SQLITE_ID) {
    throw new SseParseError("E_SSE_ID");
  }
  if (eventType === null || eventType === "" || data.length === 0) {
    throw new SseParseError("E_SSE_ENVELOPE");
  }
  let raw: unknown;
  try {
    raw = JSON.parse(data.join("\n"));
  } catch {
    throw new SseParseError("E_SSE_JSON");
  }
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new SseParseError("E_SSE_EVENT");
  }
  const item = raw as Record<string, unknown>;
  const id = Number(idText);
  const positiveInteger = (value: unknown): value is number =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
  const nullableIdentifier = (value: unknown): value is string | null =>
    value === null || (typeof value === "string" && value !== "");
  if (
    !Number.isSafeInteger(id)
    || id < 1
    || item.id !== id
    || item.type !== eventType
    || typeof item.aggregate_type !== "string"
    || item.aggregate_type === ""
    || typeof item.aggregate_id !== "string"
    || item.aggregate_id === ""
    || !positiveInteger(item.aggregate_version)
    || !nullableIdentifier(item.run_id)
    || !(item.run_seq === null || (item.run_id !== null && positiveInteger(item.run_seq)))
    || !nullableIdentifier(item.action_id)
    || typeof item.occurred_at !== "string"
    || item.occurred_at === ""
    || !(item.payload === null || (typeof item.payload === "object" && !Array.isArray(item.payload)))
  ) {
    throw new SseParseError("E_SSE_EVENT");
  }
  return {
    id,
    aggregate_type: item.aggregate_type,
    aggregate_id: item.aggregate_id,
    aggregate_version: item.aggregate_version,
    run_id: item.run_id,
    run_seq: item.run_seq,
    action_id: item.action_id,
    type: eventType,
    payload: item.payload as Record<string, unknown> | null,
    occurred_at: item.occurred_at,
  };
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<ProjectionEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      try {
        buffer += decoder.decode(value, { stream: true });
      } catch {
        throw new SseParseError("E_SSE_UTF8");
      }
      for (let marker = boundary(buffer); marker !== null; marker = boundary(buffer)) {
        const frame = buffer.slice(0, marker.index);
        buffer = buffer.slice(marker.index + marker.length);
        const event = eventFromFrame(frame);
        if (event !== null) yield event;
      }
    }
    try {
      buffer += decoder.decode();
    } catch {
      throw new SseParseError("E_SSE_UTF8");
    }
    if (buffer.trim() !== "") throw new SseParseError("E_SSE_TRUNCATED");
  } finally {
    reader.releaseLock();
  }
}
