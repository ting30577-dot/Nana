import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { ProjectionState } from "./projection";
import type { ProjectionStore, StudioState } from "./store";
import { JourneyWorkbench } from "./JourneyWorkbench";
import { ExportWorkbench } from "./ExportWorkbench";
import { connectionLabel, valueLabel } from "./uiText";

type Fact = Record<string, unknown>;

const asRows = (snapshot: Record<string, unknown> | null, key: string): Fact[] => {
  const value = snapshot?.[key];
  return Array.isArray(value) ? value.filter((item): item is Fact => item !== null && typeof item === "object" && !Array.isArray(item)) : [];
};

const text = (value: unknown, fallback = "未记录"): string =>
  typeof value === "string" && value !== "" ? value : typeof value === "number" ? String(value) : fallback;

function StateBadge({ value }: { value: unknown }) {
  const raw = text(value, "unknown");
  return <span className={`state-badge state-${raw.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}>{valueLabel(raw, "未知")}</span>;
}

function FactList({ rows, empty }: { rows: Fact[]; empty: string }) {
  if (rows.length === 0) return <p className="empty-note">{empty}</p>;
  return (
    <ol className="fact-list">
      {rows.map((row, index) => (
        <li key={text(row.id, String(index))}>
          <div className="fact-title">{text(row.title ?? row.question ?? row.statement ?? row.id)}</div>
          <div className="fact-meta">
            {row.status !== undefined && <StateBadge value={row.status} />}
            {row.revision !== undefined && <span>修订版 {text(row.revision)}</span>}
            {row.producer_run_id !== undefined && <span>来源运行 {text(row.producer_run_id)}</span>}
            {Array.isArray(row.evidence_ids) && <span>证据 {row.evidence_ids.length ? row.evidence_ids.map((id) => text(id)).join(", ") : "未记录"}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}

function PlanList({ rows }: { rows: Fact[] }) {
  if (rows.length === 0) return <p className="empty-note">尚未记录正式计划。</p>;
  return (
    <ol className="fact-list">
      {rows.map((plan, index) => {
        const steps = Array.isArray(plan.steps)
          ? plan.steps.filter((step): step is Fact => step !== null && typeof step === "object" && !Array.isArray(step))
          : [];
        return (
          <li key={text(plan.id, String(index))}>
            <div className="fact-title">{text(plan.id)} · 修订版 {text(plan.revision)}</div>
            {plan.status !== undefined && <div className="fact-meta"><StateBadge value={plan.status} /></div>}
            {steps.length === 0 ? <p className="empty-note">尚未记录计划步骤。</p> : (
              <ol className="step-list">
                {steps.map((step, stepIndex) => (
                  <li key={text(step.id, String(stepIndex))}>
                    <strong>{text(step.title ?? step.id)}</strong>
                    <span>步骤 {text(step.id)} · 需要审批：{step.approval_required === true ? "是" : "否"}</span>
                  </li>
                ))}
              </ol>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function ExecutionTrace({ projection }: { projection: ProjectionState | null }) {
  const runs = Object.values(projection?.runs ?? {});
  const actions = Object.values(projection?.actions ?? {});
  const artifacts = Object.values(projection?.artifacts ?? {});
  const receipts = Object.values(projection?.receipts ?? {});
  return (
    <ol className="trace-list">
      {runs.map((run) => (
        <li key={`run-${text(run.id)}`}>
          <strong>运行 {text(run.id)}</strong>
          <span>正式运行状态</span>
          <StateBadge value={run.state} />
        </li>
      ))}
      {actions.map((action) => (
        <li key={`action-${text(action.id)}`}>
          <strong>{text(action.capability_id, "已记录操作")}</strong>
          <span>{text(action.id)} · 步骤 {text(action.plan_step_id)}</span>
          <StateBadge value={action.state} />
        </li>
      ))}
      {artifacts.map((artifact) => (
        <li key={`artifact-${text(artifact.id)}`}>
          <strong>{text(artifact.id)}</strong>
          <span>产物 · 来源运行 {text(artifact.producer_run_id)}</span>
          <StateBadge value={artifact.state} />
        </li>
      ))}
      {receipts.map((receipt) => (
        <li key={`receipt-${text(receipt.id)}`}>
          <strong>{text(receipt.id)}</strong>
          <span>操作 {text(receipt.action_id)} · 耗时 {text((receipt.resource_usage as Fact | undefined)?.wall_clock_ms, "未记录")} 毫秒</span>
          <StateBadge value={receipt.result} />
        </li>
      ))}
    </ol>
  );
}

function summarize(projection: ProjectionState | null) {
  const actions = Object.values(projection?.actions ?? {});
  const runs = Object.values(projection?.runs ?? {});
  const receipts = Object.values(projection?.receipts ?? {});
  const stateOf = (item: Fact) => text(item.state, "unknown");
  const resultOf = (item: Fact) => text(item.result, "unknown");
  return {
    needsYou: Object.keys(projection?.needs_you ?? {}).length,
    running: runs.filter((item) => stateOf(item) === "running").length,
    failed: [
      ...runs,
      ...actions,
    ].filter((item) => ["failed", "orphaned", "budget_exceeded", "effect_unknown", "timed_out"].includes(stateOf(item))).length
      + receipts.filter((receipt) => ["failed", "effect_unknown", "timed_out"].includes(resultOf(receipt))).length,
  };
}

function ConnectionPanel({ state, store }: { state: StudioState; store: ProjectionStore }) {
  const statusRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (state.focusRevision > 0) statusRef.current?.focus();
  }, [state.focusRevision]);
  const terminal = ["stream_disconnected", "projection_unavailable", "session_expired"].includes(state.phase);
  return (
    <section className={`connection-strip phase-${state.phase}`} aria-labelledby="projection-status-heading">
      <div>
        <p className="eyebrow">投影连接</p>
        <h2 id="projection-status-heading" ref={statusRef} tabIndex={-1}>{connectionLabel(state.phase)}</h2>
      </div>
      <p className="connection-message" role="status" aria-live="polite" aria-atomic="true">{state.announcement}</p>
      {state.errorCode && <code>{state.errorCode}</code>}
      {state.phase === "stream_disconnected" && <button type="button" onClick={() => store.reconnect()}>重新连接事件流</button>}
      {terminal && state.phase !== "stream_disconnected" && <span className="terminal-mark">需要重新启动会话</span>}
    </section>
  );
}

function CausalityRail({ projection, snapshot }: { projection: ProjectionState | null; snapshot: Record<string, unknown> | null }) {
  const actions = Object.values(projection?.actions ?? {}).slice(0, 3);
  const events = projection?.activity.slice(-4) ?? [];
  const artifacts = Object.values(projection?.artifacts ?? {});
  const findings = Object.values(projection?.findings ?? {});
  const producedArtifacts = artifacts.filter((row) => typeof row.producer_run_id === "string");
  const otherArtifacts = artifacts.filter((row) => typeof row.producer_run_id !== "string");
  const receipts = Object.values(projection?.receipts ?? {}).slice(0, 3);
  const steps = asRows(snapshot, "plans").flatMap((plan) =>
    Array.isArray(plan.steps)
      ? plan.steps.filter((step): step is Fact => step !== null && typeof step === "object" && !Array.isArray(step))
      : [],
  ).slice(0, 3);
  const columns = [
    { label: "计划步骤", rows: steps.map((row) => ({ primary: text(row.title ?? row.id), relation: `步骤 ${text(row.id)}`, state: undefined })) },
    { label: "操作 / 测试", rows: actions.map((row) => ({ primary: text(row.capability_id, text(row.id)), relation: `步骤 ${text(row.plan_step_id)} → 操作 ${text(row.id)}`, state: row.state })) },
    { label: "正式事件", rows: events.map((row) => ({ primary: row.type, relation: `事件 #${row.id} · 操作 ${text(row.action_id)} · 运行 ${text(row.run_id)}`, state: undefined })) },
    { label: "产物 / 发现", rows: [...producedArtifacts, ...findings, ...otherArtifacts].slice(0, 4).map((row) => ({ primary: text(row.statement ?? row.id), relation: row.statement !== undefined ? `发现 ${text(row.id)} · 来源运行 ${text(row.producer_run_id)}` : `产物 ${text(row.id)} · 来源运行 ${text(row.producer_run_id)}`, state: row.state ?? row.status })) },
    { label: "回执", rows: receipts.map((row) => ({ primary: text(row.id), relation: `操作 ${text(row.action_id)} → 结果 ${valueLabel(row.result)}`, state: row.result })) },
  ];
  return (
    <section className="rail" aria-labelledby="rail-heading">
      <div className="section-heading"><p className="eyebrow">按因果关系，而非时间顺序</p><h2 id="rail-heading">证据链</h2></div>
      <div className="rail-grid">
        {columns.map((column, columnIndex) => (
          <div className="rail-column" key={column.label}>
            <h3><span>{String(columnIndex + 1).padStart(2, "0")}</span>{column.label}</h3>
            {column.rows.length === 0 ? <p className="rail-empty">未记录</p> : column.rows.map((row, index) => (
              <article key={`${column.label}-${index}`}>
                <strong>{row.primary}</strong>
                <small className="rail-relation">{row.relation}</small>
                {row.state !== undefined && <StateBadge value={row.state} />}
              </article>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

export function App({ store }: { store: ProjectionStore }) {
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => {
    store.start();
    void store.initializeMutations();
    return () => store.stop();
  }, [store]);
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") store.refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [store]);
  const summary = useMemo(() => summarize(state.projection), [state.projection]);
  const [localPlanNote, setLocalPlanNote] = useState("");
  const workspace = state.snapshot?.workspace as Fact | null | undefined;
  const inquiries = asRows(state.snapshot, "inquiries");
  const plans = asRows(state.snapshot, "plans");
  const resources = asRows(state.snapshot, "resources");
  const locators = asRows(state.snapshot, "locators");
  const claims = asRows(state.snapshot, "claims");
  const evidence = asRows(state.snapshot, "evidence");
  const findings = Object.values(state.projection?.findings ?? {});
  const effectUnknown = [
    ...Object.values(state.projection?.actions ?? {}),
    ...Object.values(state.projection?.runs ?? {}),
  ].some((item) => item.state === "effect_unknown")
    || Object.values(state.projection?.receipts ?? {}).some((receipt) => receipt.result === "effect_unknown");

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="wordmark"><span>N</span><div><strong>Nana</strong><small>研究控制室</small></div></div>
        <div className="workspace-stamp"><span>工作区</span><strong>{text(workspace?.id, "不可用")}</strong><StateBadge value={workspace?.status} /></div>
      </header>
      <main>
        <ConnectionPanel state={state} store={store} />
        {state.projection?.projection_status === "degraded" && (
          <section className="projection-degraded" role="status" aria-labelledby="projection-degraded-heading">
            <p className="eyebrow">正式事件需要新版投影</p>
            <h2 id="projection-degraded-heading">需要升级投影</h2>
            <p>
              活动记录已保留该事件，但当前客户端无法从中推导领域状态。
              依赖此视图前，请启动更新版本的会话。
            </p>
          </section>
        )}
        {effectUnknown && (
          <section className="quarantine" role="alert" aria-labelledby="quarantine-heading">
            <p className="eyebrow">需要你处理 · 已隔离事实</p>
            <h2 id="quarantine-heading">执行结果未知</h2>
            <p>运行时无法核实副作用。本界面不能重试、继续、忽略或将其标记为成功。</p>
          </section>
        )}
        <section className="cockpit" aria-labelledby="cockpit-heading">
          <div className="section-heading"><p className="eyebrow">当前现场状态</p><h1 id="cockpit-heading">研究驾驶舱</h1></div>
          <div className="metric-grid">
            <article><span>活跃工作区</span><strong>{workspace?.status === "active" ? "01" : "00"}</strong><small>已存储生命周期</small></article>
            <article><span>需要你处理</span><strong>{String(summary.needsYou).padStart(2, "0")}</strong><small>仅统计等待审批</small></article>
            <article><span>运行中</span><strong>{String(summary.running).padStart(2, "0")}</strong><small>正式运行</small></article>
            <article><span>失败 / 不确定</span><strong>{String(summary.failed).padStart(2, "0")}</strong><small>绝不改写为成功</small></article>
          </div>
        </section>
        <JourneyWorkbench state={state} store={store} />
        <ExportWorkbench state={state} store={store} />
        <CausalityRail projection={state.projection} snapshot={state.snapshot} />
        <section className="studio" aria-labelledby="studio-heading">
          <div className="section-heading"><p className="eyebrow">来源 → 工作 → 结果</p><h2 id="studio-heading">研究工作台</h2></div>
          <div className="studio-grid">
            <section><h3>研究问题与溯源</h3><FactList rows={[...inquiries, ...resources, ...locators, ...claims, ...evidence]} empty="尚未记录溯源事实。" /></section>
            <section>
              <h3>计划修订</h3>
              <PlanList rows={plans} />
              <div className="local-draft">
                <label htmlFor="local-plan-note">本地草稿 — 未保存</label>
                <textarea id="local-plan-note" value={localPlanNote} onChange={(event) => setLocalPlanNote(event.target.value)} placeholder="仅保留在当前浏览器标签页的私人笔记" rows={3} />
                <small>{localPlanNote === "" ? "没有本地草稿。" : "本地文字尚未保存；正式计划未改变。"}</small>
              </div>
            </section>
            <section><h3>研究发现</h3><FactList rows={findings} empty="尚未记录发现草稿。" /></section>
            <section className="execution-panel"><h3>测试、产物与回执</h3><ExecutionTrace projection={state.projection} /></section>
            <section className="activity-panel"><h3>活动记录</h3>{state.projection?.activity.length ? <ol className="activity-list">{state.projection.activity.slice().reverse().map((event) => <li key={event.id}><time>{event.occurred_at ?? "未记录时间"}</time><strong>{event.type}</strong><span>#{event.id} · {event.aggregate_type}</span></li>)}</ol> : <p className="empty-note">尚未记录已提交事件。</p>}</section>
          </div>
        </section>
      </main>
      <footer><span>正式事实 + 类型化草稿</span><span>事件游标 {state.projection?.high_water_event_id ?? 0}</span><span>一次一条命令 · 随后核对</span></footer>
    </div>
  );
}
