import { useEffect, useMemo, useState } from "react";
import type { JourneyCommand, ProjectionStore, StudioState } from "./store";
import { mutationLabel, valueLabel } from "./uiText";

type Fact = Record<string, unknown>;

const FROZEN_SOURCE = {
  logicalRef: "fixtures/v0.3.0-dev/resources/variable-window-monotonicity.md",
  mediaType: "text/markdown",
  quoteHash: `sha256:b2a8bd097c6ea04f9439745767a77df876fc1e860aa3ad71ea158f6f93c8cfe5`,
  startLine: 6,
  endLine: 12,
  claim: "For non-negative input, extending the right edge cannot decrease the window sum.",
};

const LOCKED_TEST_ID = "tests.test_sliding_window.VariableWindowTests.test_finds_shortest_matching_window";

const LOCKED_BUDGET = {
  cpu_seconds: null,
  gpu_seconds: null,
  memory_bytes: null,
  network_targets: [],
  read_roots: [],
  write_roots: [],
  wall_clock_seconds: 60,
  max_actions: 1,
  max_concurrency: 1,
  max_model_calls: 0,
  max_model_tokens: 0,
  max_cost_micros: 0,
  max_retries: 0,
  max_output_bytes: 4096,
  max_artifact_bytes: 4096,
  max_download_bytes: 0,
};

function rows(snapshot: Record<string, unknown> | null, key: string): Fact[] {
  const value = snapshot?.[key];
  return Array.isArray(value)
    ? value.filter((item): item is Fact => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function revision(value: Fact | undefined): number {
  return typeof value?.revision === "number" ? value.revision : 0;
}

function newCommandId(): string {
  return crypto.randomUUID();
}

function MutationNotice({ state, store }: { state: StudioState; store: ProjectionStore }) {
  const mutation = state.mutation;
  const uncertain = mutation.phase === "outcome_unknown";
  return (
    <div className={`command-notice command-${mutation.phase}`} role={mutation.phase === "rejected" || uncertain ? "alert" : undefined} aria-live="polite">
      <div>
        <span>{mutationLabel(mutation.phase)}</span>
        <strong>{mutation.message}</strong>
      </div>
      {mutation.errorCode && <code>{mutation.errorCode}</code>}
      {mutation.details && <details><summary>错误详情</summary><pre>{JSON.stringify(mutation.details, null, 2)}</pre></details>}
      {uncertain && <button type="button" onClick={() => void store.retryLastCommand()}>使用相同命令 ID 重试</button>}
    </div>
  );
}

function StageNumber({ value, done }: { value: number; done: boolean }) {
  return <span className={done ? "stage-number stage-done" : "stage-number"}>{done ? "✓" : String(value).padStart(2, "0")}</span>;
}

export function JourneyWorkbench({ state, store }: { state: StudioState; store: ProjectionStore }) {
  const workspace = state.snapshot?.workspace as Fact | null | undefined;
  const projects = rows(state.snapshot, "projects");
  const inquiries = rows(state.snapshot, "inquiries");
  const resources = rows(state.snapshot, "resources");
  const locators = rows(state.snapshot, "locators");
  const claims = rows(state.snapshot, "claims");
  const evidence = rows(state.snapshot, "evidence");
  const plans = rows(state.snapshot, "plans");
  const findings = rows(state.snapshot, "findings");
  const project = projects.at(-1);
  const inquiry = inquiries.at(-1);
  const resource = resources.at(-1);
  const locator = locators.at(-1);
  const claim = claims.at(-1);
  const plan = plans.at(-1);
  const projectedRuns = Object.values(state.projection?.runs ?? {});
  const runCreationOrder = new Map(
    (state.projection?.activity ?? [])
      .filter((event) => event.aggregate_type === "run" && event.type === "run.created")
      .map((event) => [event.aggregate_id, event.id]),
  );
  const orderedRuns = [...projectedRuns].sort(
    (left, right) => (runCreationOrder.get(stringValue(left.id)) ?? 0) - (runCreationOrder.get(stringValue(right.id)) ?? 0),
  );
  const terminalRun = [...orderedRuns].reverse().find((run: Fact) =>
    ["succeeded", "failed", "cancelled", "timed_out", "budget_exceeded", "orphaned"].includes(stringValue(run.state)),
  );
  const activeRun = [...orderedRuns].reverse().find((run: Fact) =>
    ["proposed", "queued", "running", "paused"].includes(stringValue(run.state)),
  );
  const enabled = useMemo(() => new Set(state.mutation.enabledCommands), [state.mutation.enabledCommands]);
  const busy = ["submitting", "accepted", "reconciling"].includes(state.mutation.phase);
  const mutationsReady = state.phase === "live" && state.projection?.projection_status === "ready" && state.mutation.phase !== "unavailable";

  const [projectTitle, setProjectTitle] = useState("可变长度滑动窗口边界");
  const [question, setQuestion] = useState("为什么可变长度滑动窗口方法依赖非负输入？");
  const [acceptance, setAcceptance] = useState("固定公开来源可以解析，锁定计划仍可编辑，且研究发现可追溯到正式执行记录。");
  const [planTitle, setPlanTitle] = useState("运行固定的非负可变窗口测试");
  const [findingStatement, setFindingStatement] = useState("固定溯源材料支持开发测试中的非负单调性前提。");
  const [confidenceBasis, setConfidenceBasis] = useState("已核验的来源范围和锁定测试的终态回执均为正式、确定性记录。");
  const [cancelReason, setCancelReason] = useState("用户取消了当前开发运行。");
  const [pauseReason, setPauseReason] = useState("用户暂停了当前开发运行。");
  const [planDirty, setPlanDirty] = useState(false);

  useEffect(() => {
    if (!planDirty && plan) {
      const steps = Array.isArray(plan.steps) ? plan.steps as Fact[] : [];
      const canonicalTitle = stringValue(steps[0]?.title);
      if (canonicalTitle) setPlanTitle(canonicalTitle);
    }
  }, [plan, planDirty]);

  const submit = async (command: JourneyCommand): Promise<boolean> => {
    const result = await store.submitCommand(command);
    return result !== null;
  };

  const commandEnabled = (name: JourneyCommand["type"]): boolean =>
    mutationsReady && !busy && enabled.has(name);

  return (
    <section className="workbench" aria-labelledby="workbench-heading">
      <div className="section-heading workbench-heading">
        <div><p className="eyebrow">本地起草 · 正式提交</p><h2 id="workbench-heading">研究旅程工作台</h2></div>
        <p>每次只执行一条类型化命令。初始化核对返回正式事实前，已接受命令不会显示为成功。</p>
      </div>
      <MutationNotice state={state} store={store} />
      <div className="journey-stages">
        <form className="journey-card" onSubmit={(event) => {
          event.preventDefault();
          if (!workspace) return;
          void submit({
            type: "CreateProject",
            command_id: newCommandId(),
            expected_revision: revision(workspace),
            workspace_id: stringValue(workspace.id),
            title: projectTitle.trim(),
            data_class: "public",
          });
        }}>
          <StageNumber value={1} done={Boolean(project)} />
          <div className="journey-card-body">
            <h3>创建公开项目</h3>
            <label htmlFor="project-title">项目标题</label>
            <input id="project-title" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} disabled={Boolean(project) || busy} required maxLength={240} />
            <button type="submit" disabled={Boolean(project) || !workspace || !projectTitle.trim() || !commandEnabled("CreateProject")}>创建项目</button>
            <small>{project ? `正式项目 ${stringValue(project.id)}` : "接受并核对前，标题仅保存在本地。"}</small>
          </div>
        </form>

        <form className="journey-card" onSubmit={(event) => {
          event.preventDefault();
          if (!project) return;
          void submit({
            type: "CreateInquiry",
            command_id: newCommandId(),
            expected_revision: revision(project),
            project_id: stringValue(project.id),
            question: question.trim(),
            acceptance: acceptance.trim(),
          });
        }}>
          <StageNumber value={2} done={Boolean(inquiry)} />
          <div className="journey-card-body">
            <h3>界定研究问题</h3>
            <label htmlFor="inquiry-question">研究问题</label>
            <textarea id="inquiry-question" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={Boolean(inquiry) || busy} required rows={3} maxLength={4000} />
            <label htmlFor="inquiry-acceptance">验收标准</label>
            <textarea id="inquiry-acceptance" value={acceptance} onChange={(event) => setAcceptance(event.target.value)} disabled={Boolean(inquiry) || busy} required rows={3} maxLength={8000} />
            <button type="submit" disabled={Boolean(inquiry) || !project || !question.trim() || !acceptance.trim() || !commandEnabled("CreateInquiry")}>创建研究问题</button>
            <small>{inquiry ? `正式研究问题 ${stringValue(inquiry.id)}` : "草稿文字仅保存在当前浏览器标签页。"}</small>
          </div>
        </form>

        <article className="journey-card provenance-card">
          <StageNumber value={3} done={Boolean(resource && locator && claim && evidence.length)} />
          <div className="journey-card-body">
            <h3>建立溯源链</h3>
            <p>运行时只接受固定公开来源及其已核验的精确范围。</p>
            <ol className="micro-steps">
              <li><span>{resource ? "✓" : "A"}</span><button type="button" disabled={Boolean(resource) || !project || !commandEnabled("RegisterResource")} onClick={() => {
                if (!project) return;
                void submit({ type: "RegisterResource", command_id: newCommandId(), expected_revision: revision(project), project_id: stringValue(project.id), kind: "local_file", logical_ref: FROZEN_SOURCE.logicalRef, media_type: FROZEN_SOURCE.mediaType, data_class: "public", license: "CC0-1.0" });
              }}>登记固定来源</button></li>
              <li><span>{locator ? "✓" : "B"}</span><button type="button" disabled={Boolean(locator) || !resource || !commandEnabled("CreateLocator")} onClick={() => {
                if (!resource) return;
                void submit({ type: "CreateLocator", command_id: newCommandId(), expected_revision: revision(resource), resource_id: stringValue(resource.id), locator_type: "local_file", coordinates: { kind: "local_file", logical_path: FROZEN_SOURCE.logicalRef, artifact_hash: stringValue(resource.content_hash), line_span: { start_line: FROZEN_SOURCE.startLine, end_line: FROZEN_SOURCE.endLine }, byte_span: null }, quote_hash: FROZEN_SOURCE.quoteHash });
              }}>核验精确来源范围</button></li>
              <li><span>{claim ? "✓" : "C"}</span><button type="button" disabled={Boolean(claim) || !inquiry || !commandEnabled("CreateClaim")} onClick={() => {
                if (!inquiry) return;
                void submit({ type: "CreateClaim", command_id: newCommandId(), expected_revision: revision(inquiry), inquiry_id: stringValue(inquiry.id), statement: FROZEN_SOURCE.claim });
              }}>创建限定论断</button></li>
              <li><span>{evidence.length ? "✓" : "D"}</span><button type="button" disabled={Boolean(evidence.length) || !inquiry || !locator || !commandEnabled("AttachEvidence")} onClick={() => {
                if (!inquiry || !locator) return;
                void submit({ type: "AttachEvidence", command_id: newCommandId(), expected_revision: revision(locator), inquiry_id: stringValue(inquiry.id), locator_id: stringValue(locator.id), direction: "supports", excerpt_hash: FROZEN_SOURCE.quoteHash });
              }}>关联正式证据</button></li>
            </ol>
            <small>界面不会暴露原始文件选择器、路径、哈希覆盖或任意定位器。</small>
          </div>
        </article>

        <form className="journey-card plan-card" onSubmit={(event) => {
          event.preventDefault();
          if (!inquiry) return;
          const shared = {
            command_id: newCommandId(),
            steps: [{ id: "step-locked-test", title: planTitle.trim(), capability_id: "python.unittest.locked", expected_artifacts: ["text/plain test result"], approval_required: false }],
            policy: { test_id: LOCKED_TEST_ID, network: "denied" },
            budget: LOCKED_BUDGET,
          };
          if (plan) {
            void submit({ ...shared, type: "RevisePlan", expected_revision: revision(plan), plan_id: stringValue(plan.id) }).then((accepted) => { if (accepted) setPlanDirty(false); });
          } else {
            void submit({ ...shared, type: "ProposePlan", expected_revision: revision(inquiry), inquiry_id: stringValue(inquiry.id) }).then((accepted) => { if (accepted) setPlanDirty(false); });
          }
        }}>
          <StageNumber value={4} done={Boolean(plan && !planDirty)} />
          <div className="journey-card-body">
            <h3>{plan ? "编辑锁定计划" : "提交锁定计划"}</h3>
            <label htmlFor="plan-step-title">可见步骤标题</label>
            <input id="plan-step-title" value={planTitle} onChange={(event) => { setPlanTitle(event.target.value); setPlanDirty(true); }} required maxLength={240} disabled={busy || Boolean(activeRun || terminalRun)} />
            <div className="frozen-contract"><span>固定能力</span><code>python.unittest.locked</code><span>网络</span><code>禁止</code><span>预算</span><code>1 次操作 / 60 秒</code></div>
            <button type="submit" disabled={!inquiry || !evidence.length || !planTitle.trim() || Boolean(activeRun || terminalRun) || !commandEnabled(plan ? "RevisePlan" : "ProposePlan")}>{plan ? "提交计划修订" : "提交计划"}</button>
            <small>{planDirty ? "本地计划文字尚未保存；正式修订版未改变。" : plan ? `正式计划修订版 ${revision(plan)}` : "请先建立溯源链。"}</small>
          </div>
        </form>

        <article className="journey-card run-card">
          <StageNumber value={5} done={Boolean(terminalRun)} />
          <div className="journey-card-body">
            <h3>运行锁定测试</h3>
            <p>后端、测试 ID、授权、效果与进程目标均由服务器注入并核验。</p>
            <button type="button" disabled={!project || !inquiry || !plan || Boolean(activeRun || terminalRun) || !commandEnabled("StartRun")} onClick={() => {
              if (!project || !inquiry || !plan) return;
              void submit({ type: "StartRun", command_id: newCommandId(), expected_revision: revision(plan), project_id: stringValue(project.id), inquiry_id: stringValue(inquiry.id), plan_id: stringValue(plan.id), plan_revision: revision(plan), random_seed: 307 });
            }}>启动锁定测试</button>
            {terminalRun && stringValue(terminalRun.state) === "failed" && <button type="button" disabled={!project || !inquiry || !plan || Boolean(activeRun) || !commandEnabled("StartRun")} onClick={() => {
              if (!project || !inquiry || !plan) return;
              void submit({ type: "StartRun", command_id: newCommandId(), expected_revision: revision(plan), project_id: stringValue(project.id), inquiry_id: stringValue(inquiry.id), plan_id: stringValue(plan.id), plan_revision: revision(plan), random_seed: 307, retry_of_run_id: stringValue(terminalRun.id) });
            }}>重试失败运行</button>}
            {activeRun && <div className="cancel-block"><label htmlFor="pause-reason">暂停 / 继续原因</label><input id="pause-reason" value={pauseReason} onChange={(event) => setPauseReason(event.target.value)} maxLength={2000} /><button type="button" disabled={!pauseReason.trim() || !commandEnabled(stringValue(activeRun.state) === "paused" ? "ResumeRun" : "PauseRun")} onClick={() => {
              const paused = stringValue(activeRun.state) === "paused";
              void submit({ type: paused ? "ResumeRun" : "PauseRun", command_id: newCommandId(), expected_revision: state.projection?.aggregate_versions[`run:${stringValue(activeRun.id)}`] ?? 1, run_id: stringValue(activeRun.id), reason: pauseReason.trim() } as JourneyCommand);
            }}>{stringValue(activeRun.state) === "paused" ? "继续当前运行" : "暂停当前运行"}</button><label htmlFor="cancel-reason">取消原因</label><input id="cancel-reason" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} maxLength={2000} /><button className="danger-button" type="button" disabled={!cancelReason.trim() || !commandEnabled("CancelRun")} onClick={() => {
              void submit({ type: "CancelRun", command_id: newCommandId(), expected_revision: state.projection?.aggregate_versions[`run:${stringValue(activeRun.id)}`] ?? 1, run_id: stringValue(activeRun.id), reason: cancelReason.trim() });
            }}>取消当前运行</button></div>}
            <small>{terminalRun ? `正式终态：${valueLabel(terminalRun.state)}` : activeRun ? `正式活动运行 ${stringValue(activeRun.id)}` : "尚未接受任何运行。"}</small>
          </div>
        </article>

        <form className="journey-card finding-card" onSubmit={(event) => {
          event.preventDefault();
          if (!inquiry || !terminalRun) return;
          void submit({ type: "DraftFinding", command_id: newCommandId(), expected_revision: revision(inquiry), inquiry_id: stringValue(inquiry.id), statement: findingStatement.trim(), confidence_basis: confidenceBasis.trim(), evidence_ids: evidence.map((item) => stringValue(item.id)), terminal_run_ids: [stringValue(terminalRun.id)] });
        }}>
          <StageNumber value={6} done={Boolean(findings.length)} />
          <div className="journey-card-body">
            <h3>起草研究发现</h3>
            <label htmlFor="finding-statement">发现陈述</label>
            <textarea id="finding-statement" value={findingStatement} onChange={(event) => setFindingStatement(event.target.value)} rows={3} maxLength={8000} required disabled={Boolean(findings.length) || busy} />
            <label htmlFor="confidence-basis">置信依据</label>
            <textarea id="confidence-basis" value={confidenceBasis} onChange={(event) => setConfidenceBasis(event.target.value)} rows={3} maxLength={8000} required disabled={Boolean(findings.length) || busy} />
            <button type="submit" disabled={Boolean(findings.length) || !inquiry || !terminalRun || !findingStatement.trim() || !confidenceBasis.trim() || !commandEnabled("DraftFinding")}>提交发现草稿</button>
            <small>{findings.length ? `正式研究发现 ${stringValue(findings.at(-1)?.id)}` : "需要正式证据和一个终态运行。"}</small>
          </div>
        </form>
      </div>
    </section>
  );
}
