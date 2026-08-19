import {
  applyProjectionEvent,
  projectionFromBootstrap,
  ProjectionError,
  type ProjectionState,
} from "./projection";
import { commandLabel } from "./uiText";
import { parseSseStream, SseParseError } from "./sse";
import type { components, operations } from "./generated/api";

export type JourneyCommand = operations["journey_command_api_v1_journey_commands_post"]["requestBody"]["content"]["application/json"];
export type JourneyCommandResult = components["schemas"]["CommandResult"];
export type RuntimeHandshake = components["schemas"]["RuntimeHandshakeResponse"];
export type ExportSelection = components["schemas"]["ExportSelectionInfo"];

export type MutationPhase =
  | "unavailable"
  | "idle"
  | "submitting"
  | "accepted"
  | "reconciling"
  | "reconciled"
  | "rejected"
  | "outcome_unknown";

export interface MutationState {
  phase: MutationPhase;
  enabledCommands: readonly string[];
  externalEffectsEnabled: boolean;
  exportSelections: readonly ExportSelection[];
  activeCommand: string | null;
  commandId: string | null;
  result: JourneyCommandResult | null;
  errorCode: string | null;
  message: string;
  details: Record<string, unknown> | null;
}

export type ConnectionPhase =
  | "idle"
  | "bootstrapping"
  | "live"
  | "reconnecting"
  | "stream_disconnected"
  | "refresh_required"
  | "projection_unavailable"
  | "session_expired";

export interface StudioState {
  phase: ConnectionPhase;
  announcement: string;
  projection: ProjectionState | null;
  snapshot: Record<string, unknown> | null;
  errorCode: string | null;
  focusRevision: number;
  mutation: MutationState;
}

export interface TransportDependencies {
  fetch: typeof globalThis.fetch;
  delay(milliseconds: number): Promise<void>;
  random(): number;
  authorization?(): string | null;
}

interface TestTransportOverride {
  delay(milliseconds: number): Promise<void>;
  random(): number;
}

declare global {
  interface Window {
    __NANA_E2E_TRANSPORT__?: unknown;
  }
}

const STREAM_DELAYS = [250, 500, 1000, 2000] as const;
const BOOTSTRAP_ATTEMPTS = 2;

function isTestOverride(value: unknown): value is TestTransportOverride {
  if (value === null || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.delay === "function" && typeof candidate.random === "function";
}

export function browserTransportDependencies(): TransportDependencies {
  const override = typeof window === "undefined" ? undefined : window.__NANA_E2E_TRANSPORT__;
  return {
    fetch: globalThis.fetch.bind(globalThis),
    delay: isTestOverride(override)
      ? (milliseconds) => override.delay(milliseconds)
      : (milliseconds) => new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds)),
    random: isTestOverride(override) ? () => override.random() : () => crypto.getRandomValues(new Uint32Array(1))[0] / 0xffffffff,
    authorization: () => {
      const value = document.querySelector<HTMLMetaElement>('meta[name="nana-local-session"]')?.content;
      return value && value.startsWith("Bearer ") ? value : null;
    },
  };
}

function jittered(base: number, random: number): number {
  const bounded = Math.min(1, Math.max(0, random));
  return Math.min(2000, Math.round(base * (0.8 + bounded * 0.4)));
}

class HttpStatusError extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
  }
}

export class ProjectionStore {
  private state: StudioState = {
    phase: "idle",
    announcement: "投影空闲",
    projection: null,
    snapshot: null,
    errorCode: null,
    focusRevision: 0,
    mutation: {
      phase: "unavailable",
      enabledCommands: [],
      externalEffectsEnabled: false,
      exportSelections: [],
      activeCommand: null,
      commandId: null,
      result: null,
      errorCode: null,
      message: "命令能力尚未加载",
      details: null,
    },
  };
  private readonly listeners = new Set<() => void>();
  private generation = 0;
  private abortController: AbortController | null = null;
  private recoveryUsed = false;
  private handshakeFlight: Promise<void> | null = null;
  private commandFlight: Promise<JourneyCommandResult | null> | null = null;
  private lastCommand: JourneyCommand | null = null;

  constructor(private readonly transport: TransportDependencies) {}

  getSnapshot = (): StudioState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  start(): void {
    this.recoveryUsed = false;
    void this.bootstrap("initial");
  }

  initializeMutations(): Promise<void> {
    if (this.handshakeFlight !== null) return this.handshakeFlight;
    this.handshakeFlight = this.loadMutationHandshake().finally(() => {
      this.handshakeFlight = null;
    });
    return this.handshakeFlight;
  }

  submitCommand(command: JourneyCommand): Promise<JourneyCommandResult | null> {
    if (this.commandFlight !== null) {
      if (this.lastCommand?.command_id === command.command_id) return this.commandFlight;
      return Promise.reject(new Error("E_COMMAND_IN_FLIGHT"));
    }
    this.lastCommand = command;
    this.commandFlight = this.performCommand(command).finally(() => {
      this.commandFlight = null;
    });
    return this.commandFlight;
  }

  retryLastCommand(): Promise<JourneyCommandResult | null> {
    if (this.lastCommand === null || this.state.mutation.phase !== "outcome_unknown") {
      return Promise.reject(new Error("E_COMMAND_NOT_RETRYABLE"));
    }
    return this.submitCommand(this.lastCommand);
  }

  reconnect(): void {
    if (this.state.phase !== "stream_disconnected") return;
    const generation = ++this.generation;
    this.abortController?.abort();
    this.abortController = new AbortController();
    this.replaceState({ phase: "reconnecting", announcement: "正在重新连接", errorCode: null });
    const cursor = this.state.projection?.high_water_event_id ?? 0;
    void this.stream(generation, cursor, 0);
  }

  /** Rebuild the canonical snapshot after a visibility/session refresh. */
  refresh(): void {
    if (this.state.phase === "projection_unavailable" || this.state.phase === "session_expired") return;
    void this.bootstrap("recovery");
  }

  stop(): void {
    this.generation += 1;
    this.abortController?.abort();
    this.abortController = null;
  }

  private requestHeaders(values: Record<string, string>): Headers {
    const headers = new Headers(values);
    const authorization = this.transport.authorization?.();
    if (authorization) headers.set("Authorization", authorization);
    return headers;
  }

  private async loadMutationHandshake(): Promise<void> {
    try {
      const response = await this.transport.fetch("/api/v1/handshake", {
        headers: this.requestHeaders({ Accept: "application/json" }),
      });
      if (response.status === 401 || response.status === 403) {
        this.terminal("session_expired", "会话已过期 — 请重新启动 Nana", `HTTP_${response.status}`);
        return;
      }
      if (!response.ok) throw new HttpStatusError(response.status);
      const raw: unknown = await response.json();
      if (raw === null || typeof raw !== "object" || Array.isArray(raw)) throw new TypeError("E_HANDSHAKE_SHAPE");
      const enabled = (raw as Record<string, unknown>).enabled_mutations;
      const commands = Array.isArray(enabled) && enabled.every((item) => typeof item === "string" && item !== "")
        ? [...new Set(enabled)].sort()
        : [];
      const row = raw as Record<string, unknown>;
      const rawSelections = row.export_selections ?? [];
      if (!Array.isArray(rawSelections)) throw new TypeError("E_HANDSHAKE_SELECTIONS");
      const selections = rawSelections.map((value): ExportSelection => {
        if (value === null || typeof value !== "object" || Array.isArray(value)) throw new TypeError("E_HANDSHAKE_SELECTION");
        const selection = value as Record<string, unknown>;
        if (
          typeof selection.selection_id !== "string"
          || !/^[A-Za-z0-9_-]{43,64}$/.test(selection.selection_id)
          || typeof selection.label !== "string"
          || selection.label.length < 1
          || selection.label.length > 240
          || typeof selection.expires_at !== "string"
          || !/^\d{4}-\d{2}-\d{2}T/.test(selection.expires_at)
          || !Number.isFinite(Date.parse(selection.expires_at))
          || (selection.provenance !== "interactive_user" && selection.provenance !== "test_harness")
        ) throw new TypeError("E_HANDSHAKE_SELECTION");
        return selection as ExportSelection;
      });
      const externalEffectsEnabled = row.external_effects_enabled === true && selections.length > 0;
      this.replaceState({
        mutation: {
          ...this.state.mutation,
          phase: commands.length ? "idle" : "unavailable",
          enabledCommands: commands,
          externalEffectsEnabled,
          exportSelections: externalEffectsEnabled ? selections : [],
          errorCode: null,
          message: commands.length ? "类型化命令通道已就绪" : "当前运行时为只读模式",
          details: null,
        },
      });
    } catch (error) {
      this.replaceState({
        mutation: {
          ...this.state.mutation,
          phase: "unavailable",
          enabledCommands: [],
          externalEffectsEnabled: false,
          exportSelections: [],
          errorCode: error instanceof HttpStatusError ? `HTTP_${error.status}` : "E_HANDSHAKE_TRANSPORT",
          message: "命令能力不可用",
          details: null,
        },
      });
    }
  }

  private async performCommand(command: JourneyCommand): Promise<JourneyCommandResult | null> {
    if (!this.state.mutation.enabledCommands.includes(command.type)) {
      this.replaceState({
        mutation: {
          ...this.state.mutation,
          phase: "rejected",
          activeCommand: command.type,
          commandId: command.command_id,
          result: null,
          errorCode: "E_COMMAND_DISABLED",
          message: "运行时握手未启用这条类型化命令",
          details: null,
        },
      });
      return null;
    }
    this.replaceState({
      mutation: {
        ...this.state.mutation,
        phase: "submitting",
        activeCommand: command.type,
        commandId: command.command_id,
        result: null,
        errorCode: null,
        message: `正在提交：${commandLabel(command.type)}`,
        details: null,
      },
    });
    try {
      const response = await this.transport.fetch("/api/v1/journey/commands", {
        method: "POST",
        headers: this.requestHeaders({ Accept: "application/json", "Content-Type": "application/json" }),
        body: JSON.stringify(command),
      });
      if (response.status === 401 || response.status === 403) {
        this.terminal("session_expired", "会话已过期 — 请重新启动 Nana", `HTTP_${response.status}`);
        this.replaceState({
          mutation: {
            ...this.state.mutation,
            phase: "rejected",
            errorCode: `HTTP_${response.status}`,
            message: "命令被接受前会话已过期",
          },
        });
        return null;
      }
      const payload: unknown = await response.json();
      if (!response.ok) {
        const error = this.structuredError(payload, response.status);
        if (response.status === 409) await this.bootstrap("recovery");
        this.replaceState({
          mutation: {
            ...this.state.mutation,
            phase: "rejected",
            result: null,
            errorCode: error.code,
            message: error.message,
            details: error.details,
          },
        });
        return null;
      }
      const result = this.commandResult(payload, command.command_id);
      this.replaceState({
        mutation: {
          ...this.state.mutation,
          phase: "accepted",
          result,
          errorCode: null,
          message: `${commandLabel(command.type)}已接受；正在核对正式事实`,
          details: null,
        },
      });
      this.replaceState({ mutation: { ...this.state.mutation, phase: "reconciling" } });
      await this.bootstrap("recovery");
      if (this.state.phase === "live") {
        this.replaceState({
          mutation: {
            ...this.state.mutation,
            phase: "reconciled",
            message: `${commandLabel(command.type)}已从正式投影完成核对`,
          },
        });
      }
      return result;
    } catch (error) {
      await this.bootstrap("recovery");
      this.replaceState({
        mutation: {
          ...this.state.mutation,
          phase: "outcome_unknown",
          result: null,
          errorCode: error instanceof SyntaxError ? "E_COMMAND_RESPONSE_JSON" : "E_COMMAND_RESPONSE_LOST",
          message: "命令响应已丢失；正式投影已经刷新。重试将使用相同的命令 ID。",
          details: null,
        },
      });
      return null;
    }
  }

  private structuredError(payload: unknown, status: number): { code: string; message: string; details: Record<string, unknown> | null } {
    if (payload !== null && typeof payload === "object" && !Array.isArray(payload)) {
      const error = (payload as Record<string, unknown>).error;
      if (error !== null && typeof error === "object" && !Array.isArray(error)) {
        const row = error as Record<string, unknown>;
        if (typeof row.code === "string" && typeof row.message === "string") {
          const safe = row.data_safe === true;
          return {
            code: row.code,
            message: safe ? row.message : "命令已被驳回；不安全的详情已隐藏",
            details: safe && row.details !== null && typeof row.details === "object" && !Array.isArray(row.details)
              ? row.details as Record<string, unknown>
              : null,
          };
        }
      }
    }
    return { code: `HTTP_${status}`, message: "命令已被驳回，但服务器未返回有效的结构化错误", details: null };
  }

  private commandResult(payload: unknown, commandId: string): JourneyCommandResult {
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) throw new TypeError("E_COMMAND_RESULT_SHAPE");
    const row = payload as Record<string, unknown>;
    if (
      row.command_id !== commandId
      || (row.status !== "accepted" && row.status !== "replayed")
      || !Array.isArray(row.event_ids)
      || row.event_ids.some((value) => typeof value !== "number" || !Number.isSafeInteger(value) || value < 1)
      || row.affected_revisions === null
      || typeof row.affected_revisions !== "object"
      || Array.isArray(row.affected_revisions)
      || Object.entries(row.affected_revisions as Record<string, unknown>).some(
        ([key, value]) => key === "" || typeof value !== "number" || !Number.isSafeInteger(value) || value < 1,
      )
    ) throw new TypeError("E_COMMAND_RESULT_SHAPE");
    return payload as JourneyCommandResult;
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }

  private replaceState(patch: Partial<StudioState>): void {
    this.state = { ...this.state, ...patch };
    this.emit();
  }

  private async bootstrap(reason: "initial" | "recovery"): Promise<void> {
    const generation = ++this.generation;
    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    this.replaceState({
      phase: reason === "recovery" ? "refresh_required" : "bootstrapping",
      announcement: reason === "recovery" ? "需要刷新投影" : "正在加载正式投影",
      errorCode: null,
    });
    for (let attempt = 0; attempt < BOOTSTRAP_ATTEMPTS; attempt += 1) {
      if (attempt > 0) await this.transport.delay(jittered(250, this.transport.random()));
      if (generation !== this.generation) return;
      try {
        const response = await this.transport.fetch("/api/v1/bootstrap", {
          headers: this.requestHeaders({ Accept: "application/json" }),
          signal: controller.signal,
        });
        if (response.status === 401 || response.status === 403) {
          this.terminal("session_expired", "会话已过期 — 请重新启动 Nana", `HTTP_${response.status}`);
          return;
        }
        if (!response.ok) throw new HttpStatusError(response.status);
        const raw: unknown = await response.json();
        if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
          throw new ProjectionError("E_BOOTSTRAP_SHAPE");
        }
        const snapshot = raw as Record<string, unknown>;
        const projection = projectionFromBootstrap(snapshot);
        if (generation !== this.generation) return;
        this.state = {
          phase: "live",
          announcement: reason === "recovery" ? "投影已刷新" : "正式投影已连接",
          projection,
          snapshot,
          errorCode: null,
          focusRevision: this.state.focusRevision + 1,
          mutation: this.state.mutation,
        };
        this.emit();
        void this.stream(generation, projection.high_water_event_id, 0);
        return;
      } catch (error) {
        if (controller.signal.aborted || generation !== this.generation) return;
        if (error instanceof ProjectionError || error instanceof SyntaxError) {
          this.terminal("projection_unavailable", "投影不可用 — 请启动新的 Nana 会话", error instanceof ProjectionError ? error.code : "E_BOOTSTRAP_JSON");
          return;
        }
        if (attempt === BOOTSTRAP_ATTEMPTS - 1) {
          this.terminal("projection_unavailable", "投影不可用 — 请启动新的 Nana 会话", error instanceof HttpStatusError ? `HTTP_${error.status}` : "E_BOOTSTRAP_TRANSPORT");
          return;
        }
      }
    }
  }

  private async stream(generation: number, cursor: number, reconnectAttempt: number): Promise<void> {
    if (generation !== this.generation) return;
    const controller = this.abortController;
    if (controller === null) return;
    try {
      const response = await this.transport.fetch("/api/v1/events", {
        headers: this.requestHeaders({ Accept: "text/event-stream", "Last-Event-ID": String(cursor) }),
        signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403) {
        this.terminal("session_expired", "会话已过期 — 请重新启动 Nana", `HTTP_${response.status}`);
        return;
      }
      if (!response.ok || response.body === null) throw new HttpStatusError(response.status);
      this.replaceState({ phase: "live", announcement: "正式事件流已连接", errorCode: null });
      for await (const event of parseSseStream(response.body)) {
        if (generation !== this.generation) return;
        const projection = this.state.projection;
        if (projection === null) throw new ProjectionError("E_PROJECTION_MISSING");
        const next = applyProjectionEvent(projection, event);
        this.replaceState({ projection: next });
        cursor = next.high_water_event_id;
        if (["action.completed", "action.cancelled", "action.effect_unknown"].includes(event.type)) {
          await this.bootstrap("recovery");
          return;
        }
      }
      throw new TypeError("event stream ended");
    } catch (error) {
      if (controller.signal.aborted || generation !== this.generation) return;
      if (error instanceof SseParseError || error instanceof ProjectionError) {
        if (this.recoveryUsed) {
          this.terminal("projection_unavailable", "投影不可用 — 请启动新的 Nana 会话", error.code);
          return;
        }
        this.recoveryUsed = true;
        await this.bootstrap("recovery");
        return;
      }
      if (reconnectAttempt >= STREAM_DELAYS.length) {
        this.terminal("stream_disconnected", "事件流已断开 — 可以手动重新连接", error instanceof HttpStatusError ? `HTTP_${error.status}` : "E_STREAM_TRANSPORT");
        return;
      }
      this.replaceState({ phase: "reconnecting", announcement: `正在重新连接（第 ${reconnectAttempt + 1}/${STREAM_DELAYS.length} 次）` });
      await this.transport.delay(jittered(STREAM_DELAYS[reconnectAttempt], this.transport.random()));
      if (generation !== this.generation) return;
      await this.stream(generation, cursor, reconnectAttempt + 1);
    }
  }

  private terminal(phase: Extract<ConnectionPhase, "stream_disconnected" | "projection_unavailable" | "session_expired">, announcement: string, errorCode: string): void {
    this.abortController?.abort();
    this.abortController = null;
    this.replaceState({ phase, announcement, errorCode });
  }
}
