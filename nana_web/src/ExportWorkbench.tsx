import { useMemo } from "react";
import type { JourneyCommand, ProjectionStore, StudioState } from "./store";
import { valueLabel } from "./uiText";

type Fact = Record<string, unknown>;

function text(value: unknown, fallback = "未记录"): string {
  return typeof value === "string" && value !== "" ? value : fallback;
}

function revision(value: Fact | undefined): number {
  return typeof value?.revision === "number" && Number.isSafeInteger(value.revision) ? value.revision : 0;
}

function shortHash(value: unknown): string {
  const full = text(value);
  return full.startsWith("sha256:") && full.length > 24 ? `${full.slice(0, 19)}…${full.slice(-8)}` : full;
}

function newCommandId(): string {
  return crypto.randomUUID();
}

export function ExportWorkbench({ state, store }: { state: StudioState; store: ProjectionStore }) {
  const findings = Object.values(state.projection?.findings ?? {});
  const approvals = Object.values(state.projection?.approvals ?? {});
  const exports = Object.values(state.projection?.exports ?? {});
  const receipts = Object.values(state.projection?.receipts ?? {});
  const finding = findings.at(-1);
  const approval = approvals.at(-1);
  const exportFact = approval
    ? exports.find((item) => item.action_id === approval.subject_id)
    : exports.at(-1);
  const receipt = exportFact
    ? receipts.find((item) => item.action_id === exportFact.action_id)
    : undefined;
  const selection = state.mutation.exportSelections[0];
  const enabled = useMemo(() => new Set(state.mutation.enabledCommands), [state.mutation.enabledCommands]);
  const busy = ["submitting", "accepted", "reconciling"].includes(state.mutation.phase);
  const ready = state.phase === "live" && state.projection?.projection_status === "ready" && !busy;
  const decision = text(approval?.decision, "unrequested");
  const actionState = text(exportFact?.state, "not prepared");
  const receiptResult = text(receipt?.result, "pending");
  const uncertain = receiptResult === "effect_unknown" || actionState === "effect_unknown";
  const canPrepare = Boolean(
    ready
    && finding
    && !approval
    && selection
    && state.mutation.externalEffectsEnabled
    && enabled.has("RequestApproval"),
  );
  const canDecide = Boolean(
    ready
    && approval
    && decision === "requested"
    && approval.consumed !== true
    && revision(approval) > 0
    && text(approval.subject_hash, "")
    && enabled.has("DecideApproval"),
  );

  const submit = (command: JourneyCommand) => void store.submitCommand(command);
  const decide = (value: "approved" | "denied") => {
    if (!approval || !canDecide) return;
    submit({
      type: "DecideApproval",
      command_id: newCommandId(),
      expected_revision: revision(approval),
      approval_id: text(approval.id),
      subject_hash: text(approval.subject_hash),
      decision: value,
    });
  };

  return (
    <section className="export-workbench" aria-labelledby="export-heading">
      <div className="section-heading export-heading">
        <div><p className="eyebrow">一次审批 · 一份固定本地草稿</p><h2 id="export-heading">受控草稿导出</h2></div>
        <p>浏览器不能选择路径、能力、文件名、字节内容或授权；它只能引用启动器提供的、不透明且已脱敏的选择。</p>
      </div>

      <div className="export-ledger">
        <article className="export-target-card">
          <span className="ledger-index">01</span>
          <h3>启动器选择</h3>
          {selection ? (
            <>
              <strong>{selection.label}</strong>
              <dl><div><dt>过期时间</dt><dd>{selection.expires_at}</dd></div><div><dt>来源</dt><dd>{selection.provenance === "interactive_user" ? "交互式启动器" : "显式测试工具"}</dd></div></dl>
              <small>不透明标识仅保留在当前本地会话中；投影不会暴露绝对路径。</small>
            </>
          ) : <p className="empty-note">没有启动器签发的有效目标选择。请重启交互式启动器后再导出。</p>}
        </article>

        <article className="export-approval-card">
          <span className="ledger-index">02</span>
          <h3>审批对象</h3>
          {!approval ? (
            <>
              <p>根据正式研究发现及其成功的来源运行，准备一份仅包含公开数据的确定性 Markdown 草稿。</p>
              <button type="button" disabled={!canPrepare} onClick={() => {
                if (!finding || !selection) return;
                submit({
                  type: "RequestApproval",
                  command_id: newCommandId(),
                  expected_revision: revision(finding),
                  finding_id: text(finding.id),
                  target_selection_id: selection.selection_id,
                });
              }}>准备受控草稿导出</button>
              <small>{finding ? `正式研究发现 ${text(finding.id)}` : "请先创建正式研究发现。"}</small>
            </>
          ) : (
            <>
              <dl>
                <div><dt>决定</dt><dd><span className={`state-badge state-${decision}`}>{valueLabel(decision)}</span></dd></div>
                <div><dt>能力</dt><dd>{text(approval.capability_id)}</dd></div>
                <div><dt>风险</dt><dd>{text(approval.risk_tier)}</dd></div>
                <div><dt>对象</dt><dd><code title={text(approval.subject_hash)}>{shortHash(approval.subject_hash)}</code></dd></div>
                <div><dt>过期时间</dt><dd>{text(approval.expires_at)}</dd></div>
                <div><dt>已使用</dt><dd>{approval.consumed === true ? "是 · 仅一次" : "否"}</dd></div>
              </dl>
              {decision === "requested" && (
                <div className="approval-actions">
                  <button type="button" disabled={!canDecide} onClick={() => decide("approved")}>批准一次性草稿</button>
                  <button type="button" className="danger-button" disabled={!canDecide} onClick={() => decide("denied")}>拒绝导出</button>
                </div>
              )}
              {decision === "denied" && <p className="terminal-copy">正式拒绝。系统未创建授权，导出运行已取消。</p>}
              {decision === "expired" && <p className="terminal-copy">正式审批已过期。系统未创建授权；请用新的目标选择重新启动，再尝试导出。</p>}
            </>
          )}
        </article>

        <article className={`export-receipt-card ${uncertain ? "receipt-uncertain" : ""}`}>
          <span className="ledger-index">03</span>
          <h3>正式回执</h3>
          {receipt ? (
            <dl>
              <div><dt>结果</dt><dd><span className={`state-badge state-${receiptResult}`}>{valueLabel(receiptResult)}</span></dd></div>
              <div><dt>操作</dt><dd>{text(receipt.action_id)}</dd></div>
              <div><dt>计费依据</dt><dd>{text(receipt.billing_basis)}</dd></div>
              <div><dt>写入栅栏</dt><dd>{exportFact?.write_fenced === 1 ? "已提交" : "未提交"}</dd></div>
              <div><dt>输出字节数</dt><dd>{typeof (receipt.resource_usage as Fact | undefined)?.output_bytes === "number" ? String((receipt.resource_usage as Fact).output_bytes) : "未记录"}</dd></div>
            </dl>
          ) : exportFact ? (
            <p className="empty-note">正式导出操作：{valueLabel(actionState)}。正在等待操作终态及其正式回执。</p>
          ) : <p className="empty-note">尚未记录导出操作或回执。</p>}
          {uncertain && <div className="uncertain-lock" role="alert"><strong>执行结果未知 · 已隔离</strong><p>这里没有重试、继续、重新绑定、忽略或标记成功的控件。再次导出需要新的启动器选择和一条全新的执行链。</p></div>}
          {receiptResult === "succeeded" && <p className="terminal-copy">正式回执确认固定草稿已写入。浏览器没有写入或核验该文件。</p>}
          {receiptResult === "failed" && <p className="terminal-copy">正式结果为失败。运行时没有报告成功。</p>}
        </article>
      </div>
    </section>
  );
}
