const VALUE_LABELS: Record<string, string> = {
  active: "正常",
  accepted: "已接受",
  approved: "已批准",
  archived: "已归档",
  available: "可用",
  blocked: "受阻",
  budget_exceeded: "超出预算",
  cancelled: "已取消",
  closed: "已关闭",
  committed: "已提交",
  completed: "已完成",
  confirmed: "已确认",
  contested: "有争议",
  degraded: "降级",
  denied: "已拒绝",
  deprecated: "已弃用",
  draft: "草稿",
  effect_unknown: "结果未知",
  expired: "已过期",
  failed: "失败",
  falsified: "已证伪",
  in_review: "审核中",
  inconclusive: "无定论",
  invalid: "无效",
  lead: "线索",
  orphaned: "失去归属",
  paused: "已暂停",
  pending: "待处理",
  proposed: "已提议",
  queued: "排队中",
  read_only: "只读",
  ready: "就绪",
  rejected: "已驳回",
  replayed: "已重放",
  requested: "待审批",
  running: "运行中",
  safe_mode: "安全模式",
  source_unavailable: "来源不可用",
  stale: "已过时",
  succeeded: "成功",
  supported: "已支持",
  superseded: "已取代",
  testing: "验证中",
  timed_out: "已超时",
  tombstoned: "已删除",
  unrequested: "未申请",
  valid: "有效",
  validated: "已验证",
  verified: "已核实",
  waiting_approval: "等待审批",
};

const CONNECTION_LABELS: Record<string, string> = {
  idle: "空闲",
  bootstrapping: "正在初始化",
  live: "已连接",
  reconnecting: "正在重连",
  stream_disconnected: "事件流已断开",
  refresh_required: "需要刷新投影",
  projection_unavailable: "投影不可用",
  session_expired: "会话已过期",
};

const MUTATION_LABELS: Record<string, string> = {
  unavailable: "命令不可用",
  idle: "等待命令",
  submitting: "正在提交",
  accepted: "已接受",
  reconciling: "正在核对",
  succeeded: "已完成",
  rejected: "已驳回",
  outcome_unknown: "命令结果未知",
};

const COMMAND_LABELS: Record<string, string> = {
  CreateProject: "创建项目",
  CreateInquiry: "创建研究问题",
  RegisterResource: "登记来源",
  CreateLocator: "创建来源定位",
  CreateClaim: "创建论断",
  AttachEvidence: "关联证据",
  ProposePlan: "提交计划",
  RevisePlan: "修订计划",
  StartRun: "启动运行",
  PauseRun: "暂停运行",
  ResumeRun: "继续运行",
  CancelRun: "取消运行",
  DraftFinding: "提交发现草稿",
  RequestApproval: "申请导出审批",
  DecideApproval: "作出审批决定",
};

export function valueLabel(value: unknown, fallback = "未记录"): string {
  if (typeof value === "number") return String(value);
  if (typeof value !== "string" || value === "") return fallback;
  return VALUE_LABELS[value] ?? value;
}

export function connectionLabel(value: string): string {
  return CONNECTION_LABELS[value] ?? value;
}

export function mutationLabel(value: string): string {
  return MUTATION_LABELS[value] ?? value;
}

export function commandLabel(value: string): string {
  return COMMAND_LABELS[value] ?? value;
}
