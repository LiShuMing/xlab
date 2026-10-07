import { useEffect, useMemo, useState } from "react";
import { Link2, Sparkles } from "lucide-react";
import type {
  DigestOptions,
  EvidenceDigest,
  Job,
  SourceRef,
  State,
} from "./api";
import { sourceRef } from "./api";

const labels: Record<string, string> = {
  queued: "待处理",
  running: "处理中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  paused: "恢复后暂停",
};
const errors: Record<string, string> = {
  NO_EVIDENCE: "没有可提取的正文段落，请补充说明。",
  INVALID_EVIDENCE: "结果未通过结构与引用校验，没有发布。",
  PROVIDER_FAILED: "处理失败，可在检查素材后重试。",
  LEASE_EXHAUSTED: "任务多次中断，已达到尝试上限。",
  POLICY_BLOCKED: "素材策略禁止当前处理方式。",
  PROVIDER_DISABLED: "模型服务未启用。",
  SOURCE_BLOB_INVALID: "来源原件缺失或损坏，请在设置中检查完整性。",
  LLM_AUTH_FAILED: "服务拒绝认证，请检查配置；不会显示或记录密钥。",
  LLM_RATE_LIMIT: "模型服务限流，没有自动重发。",
  LLM_TIMEOUT: "请求超时，可能已消耗额度；请确认后手动重试。",
  LLM_NETWORK_FAILED: "模型网络请求失败，是否已计费不确定。",
  LLM_HTTP_FAILED: "模型服务返回错误，请检查模型与接口配置。",
  LLM_INVALID_RESPONSE: "模型响应结构不合法，未发布结果。",
  LLM_OUTPUT_INCOMPLETE: "模型输出未完整结束，未发布结果。",
  LLM_REDIRECT_BLOCKED: "接口重定向被拒绝，密钥不会转发到其他地址。",
  LLM_PROFILE_CHANGED: "服务或模型已变化，请重新授权并创建新任务。",
  CALL_INTERRUPTED: "请求被中断，费用不确定；不会自动重发。",
  CALL_CANCELLED: "请求已中止，已发内容无法撤回。",
};

export function DigestCard({
  digest,
  onSource,
}: {
  digest: EvidenceDigest;
  onSource: (ref: SourceRef) => void;
}) {
  return (
    <section className="panel evidence-digest">
      <div className="section-heading">
        <h2>
          <Sparkles size={18} />
          证据化消化
        </h2>
        <span className="tiny-tag">
          {digest.mode === "cloud_llm"
            ? `${digest.model} · 真实模型`
            : "本地 mock"}{" "}
          · 待人工复核
        </span>
      </div>
      <p className="reading-note">
        仅校验引用版本与逐字摘录，不证明来源陈述正确，也不保证引用支持归纳结论。
        {digest.mode === "cloud_llm"
          ? "真实模型生成的归纳与推断均需人工复核；不会自动覆写个人正文。"
          : "这里是离线摘录，不是实际模型的语义归纳。"}
      </p>
      {digest.coverage_state === "partial" && (
        <p role="status" className="reading-note">
          部分摘录：
          {
            digest.source_coverage.filter((s) => s.status === "no_excerpt")
              .length
          }{" "}
          份输入没有被结果引用，不能视为已完成全量归纳。请复核遗漏或补充说明。
        </p>
      )}
      {digest.output.claims.map((claim, i) => (
        <article className="claim" key={i}>
          <span className="badge gray">
            {claim.kind === "source_statement" ? "来源陈述" : "模型推断"}
          </span>
          <p>{claim.text}</p>
          {claim.citations.map((cite, n) => {
            const chunk = digest.chunks.find(
              (c) => c.chunk_id === cite.chunk_id,
            );
            if (!chunk) return <p key={n}>引用缺失，请校验备份。</p>;
            return (
              <details className="claim-evidence" key={n}>
                <summary>
                  查看证据 · {chunk.title} · v{chunk.material_revision}
                </summary>
                <blockquote>{cite.quote}</blockquote>
                <p className="reading-note">
                  第 {chunk.start_line}–{chunk.end_line} 行所在片段 · Unicode
                  偏移 [{chunk.offset}, {chunk.end})
                </p>
                <small className="hash-proof">
                  原件 SHA-256：{chunk.blob_hash}
                  <br />
                  片段 SHA-256：{chunk.chunk_hash}
                </small>
                <button className="citation" onClick={() => onSource(chunk)}>
                  <Link2 size={13} />
                  阅读此版本原文
                </button>
              </details>
            );
          })}
        </article>
      ))}
      {digest.topic_delta?.length > 0 && (
        <p className="reading-note">
          处理记录：
          {
            digest.topic_delta.filter((d) => d.status === "first_processed")
              .length
          }{" "}
          份首次处理，
          {
            digest.topic_delta.filter((d) => d.status !== "first_processed")
              .length
          }{" "}
          份原件已处理过。不是“新知识 / 观点重复”的判断。
        </p>
      )}
      <div className="question-box">
        <h3>待验证问题</h3>
        {digest.output.questions.map((q) => (
          <p key={q}>{q}</p>
        ))}
      </div>
      <a
        className="button"
        href={`/api/v1/export/${digest.id}?revision=${digest.revision}&format=markdown`}
        download
      >
        导出此份消化
      </a>
    </section>
  );
}

export function ProcessingView({
  state,
  busy,
  onSubmit,
  onAction,
  onSource,
}: {
  state: State;
  busy: boolean;
  onSubmit: (refs: SourceRef[], options: DigestOptions) => void;
  onAction: (
    job: Job,
    action: "cancel" | "retry",
    cloudConsent?: boolean,
  ) => void;
  onSource: (ref: SourceRef) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [provider, setProvider] = useState<DigestOptions["provider"]>("mock");
  const [consent, setConsent] = useState(false);
  const ready = state.materials.filter((m) => m.parse_state === "ready");
  const budget = state.processing.budget;
  const cloud = state.processing.profiles.find(
    (p) => p.provider === "openai_compatible",
  );
  const chosen = ready.filter((m) => selected.includes(m.id));
  const selectionVersion = chosen.map((m) => `${m.id}:${m.revision}`).join("|");
  const inputCharacters = useMemo(
    () =>
      state.materials
        .filter((m) => selected.includes(m.id))
        .reduce((n, m) => n + Array.from(m.content).length, 0),
    [state.materials, selected],
  );
  const cloudAllowed =
    !!cloud &&
    chosen.every(
      (m) =>
        m.processing_policy === "cloud_allowed" &&
        m.cloud_allowed_profile === cloud.profile_id,
    );
  useEffect(
    () => setConsent(false),
    [provider, selectionVersion, cloud?.profile_id],
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">LAYER 1 · EVIDENCE</span>
          <h1>消化任务</h1>
          <p>固定素材版本，生成可回到原文的线索。理解与判断仍由你完成。</p>
        </div>
      </div>
      <div className="processing-grid">
        <section className="panel">
          <div className="section-heading">
            <h2>选择要消化的素材</h2>
            <span className="tiny-tag">
              {provider === "mock" ? "离线模拟" : "真实模型"}
            </span>
          </div>
          <p className="reading-note">
            最多 12 份；mock 上限 60,000 字符，API 上限 12,000
            字符。相同素材版本与模型配置复用原任务。
          </p>
          <label>
            处理模式
            <select
              aria-label="消化处理模式"
              value={provider}
              onChange={(e) =>
                setProvider(e.target.value as DigestOptions["provider"])
              }
            >
              <option value="mock">本地 mock（不外发）</option>
              {cloud && (
                <option value="openai_compatible">
                  已配置 API · {cloud.model}
                </option>
              )}
            </select>
          </label>
          {state.processing.config_error && (
            <p role="alert">
              模型配置未启用：{state.processing.config_error}
              。不会自动调用其他服务。
            </p>
          )}
          {provider === "openai_compatible" && (
            <p className="reading-note">
              目标：{cloud?.endpoint_host} · {cloud?.model}。输入{" "}
              {inputCharacters.toLocaleString()} 字符；最多输出{" "}
              {cloud?.max_tokens} tokens。需要逐素材授权并确认外发。
            </p>
          )}
          <div className="digest-selection">
            {ready.map((m) => (
              <label key={m.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(m.id)}
                  onChange={(e) =>
                    setSelected((ids) =>
                      e.target.checked
                        ? [...ids, m.id]
                        : ids.filter((id) => id !== m.id),
                    )
                  }
                  disabled={!selected.includes(m.id) && selected.length >= 12}
                />
                <span>
                  {m.title}
                  <small>
                    v{m.revision} · {m.content.length.toLocaleString()} 字符
                    {provider === "openai_compatible" &&
                      (m.processing_policy === "cloud_allowed" &&
                      m.cloud_allowed_profile === cloud?.profile_id
                        ? " · 已授权此服务"
                        : " · 未授权")}
                  </small>
                  <button
                    className="citation"
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      onSource(sourceRef(m));
                    }}
                  >
                    处理策略 / 原文
                  </button>
                </span>
              </label>
            ))}
          </div>
          {!ready.length && (
            <p className="reading-note">
              还没有可处理的正文。先收集笔记或上传 Markdown。
            </p>
          )}
          {provider === "openai_compatible" && (
            <>
              {!cloudAllowed && (
                <p className="reading-note">
                  请在所选素材的“处理策略 / 原文”中，授权当前正文给此服务。
                </p>
              )}
              <label className="cloud-consent">
                <input
                  type="checkbox"
                  checked={consent}
                  disabled={!cloudAllowed}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                我确认将所选版本的标题、正文及版本/片段引用发送给{" "}
                {cloud?.endpoint_host} / {cloud?.model}，可能消耗 API 额度。
              </label>
              {inputCharacters > 12000 && (
                <p role="alert">输入超过 API 上限，请拆分；不会静默截断。</p>
              )}
            </>
          )}
          <button
            className="button primary"
            disabled={
              busy ||
              !selected.length ||
              !ready.some((m) => selected.includes(m.id)) ||
              (provider === "openai_compatible" &&
                (!cloudAllowed || !consent || inputCharacters > 12000))
            }
            onClick={() =>
              onSubmit(
                ready.filter((m) => selected.includes(m.id)).map(sourceRef),
                {
                  provider,
                  cloud_consent: provider === "openai_compatible" && consent,
                  provider_profile:
                    provider === "openai_compatible"
                      ? cloud?.profile_id
                      : undefined,
                },
              )
            }
          >
            提交证据化消化
          </button>
        </section>
        <section className="panel">
          <h2>处理额度</h2>
          <p>
            {budget.day} ·{" "}
            {budget.cost === null
              ? "API 费用未估价，以供应商账单为准"
              : `模拟费用 ¥${budget.cost}`}
          </p>
          <div className="report-numbers">
            <span>
              已用<strong>{budget.used.toLocaleString()}</strong>
            </span>
            <span>
              预留<strong>{budget.reserved.toLocaleString()}</strong>
            </span>
            <span>
              剩余<strong>{budget.remaining.toLocaleString()}</strong>
            </span>
          </div>
          {budget.cloud && (
            <div className="cloud-budget">
              <p>
                模型请求：{budget.cloud.requests} 次已发 /{" "}
                {budget.cloud.reserved_requests} 次预留（每日上限{" "}
                {budget.cloud.request_limit}）。
              </p>
              <p>
                实际 tokens：{budget.cloud.actual_tokens.toLocaleString()}
                ；未结算预留：{budget.cloud.reserved_tokens.toLocaleString()}
                ；用量不确定的保守占用：
                {budget.cloud.uncertain_tokens.toLocaleString()}。
              </p>
              <p className="reading-note">
                每日 token 额度 {budget.cloud.token_limit.toLocaleString()}
                ，剩余 {budget.cloud.remaining_tokens.toLocaleString()}
                。超时/取消无法保证供应商未计费；没有自动付费重试。
              </p>
            </div>
          )}
          <p className="reading-note">
            上限 {budget.limit.toLocaleString()} Unicode 字符单位。预留为输入 +
            输出上限；交付 / 失败后结算，取消释放预留。这不是模型 token
            或真实费用账单。
          </p>
          <p className="reading-note">
            恢复中的任务保持暂停，需要手动重试。取消立即禁止旧 worker 交付。
          </p>
        </section>
      </div>
      <section className="panel processing-jobs">
        <div className="section-heading">
          <h2>任务记录</h2>
          <span className="tiny-tag">自动刷新状态</span>
        </div>
        {!state.jobs.length && (
          <p className="reading-note">提交后会在这里看到进度与可追溯结果。</p>
        )}
        {state.jobs.map((job) => (
          <article className="job-row" key={job.id}>
            <div>
              <strong>{labels[job.state] || job.state}</strong>
              <p>
                {job.source_refs.length} 份固定版本 · 尝试 {job.attempts}/3 ·
                fence {job.fence}
              </p>
              <small>{job.id}</small>
              <p>
                {job.provider === "openai_compatible"
                  ? `API · ${job.provider_profile?.model} · ${job.provider_profile?.endpoint_host}`
                  : "本地 mock"}
              </p>
              {job.call_attempts?.map((call) => (
                <small className="call-usage" key={call.id}>
                  {call.usage
                    ? `调用记录：输入 ${call.usage.prompt_tokens} / 输出 ${call.usage.completion_tokens} tokens`
                    : `${call.state === "in_flight" ? "请求未结算" : "usage 不确定"}：保守预留/占用 ${call.token_reservation} tokens`}{" "}
                  · {call.id}
                </small>
              ))}
              {job.error_code && (
                <p role="alert">{errors[job.error_code] || job.error_code}</p>
              )}
            </div>
            <div className="job-actions">
              {["queued", "running", "paused"].includes(job.state) && (
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => onAction(job, "cancel")}
                >
                  取消任务
                </button>
              )}
              {["failed", "cancelled", "paused"].includes(job.state) && (
                <button
                  className="button"
                  disabled={
                    busy ||
                    job.attempts >= 3 ||
                    !!job.call_attempts?.some((c) => c.state === "in_flight") ||
                    (job.provider === "openai_compatible" &&
                      job.provider_profile?.profile_id !== cloud?.profile_id)
                  }
                  onClick={() => {
                    if (
                      job.provider === "openai_compatible" &&
                      !window.confirm(
                        `重试会再次发送本任务的固定版本正文到 ${job.provider_profile?.endpoint_host} / ${job.provider_profile?.model}，可能再次消耗 API 额度。确认重试？`,
                      )
                    )
                      return;
                    onAction(
                      job,
                      "retry",
                      job.provider === "openai_compatible",
                    );
                  }}
                >
                  重试任务
                </button>
              )}
              {job.digest_id && (
                <a
                  className="button"
                  href={`#digest-${job.digest_id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    document
                      .getElementById(`digest-${job.digest_id}`)
                      ?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  查看结果
                </a>
              )}
            </div>
          </article>
        ))}
      </section>
      <p className="reading-note">
        完成的消化不会自动改写旧 Report。到“每日
        Report”手动更新，符合输入版本的结果才会被纳入；博客和图书馆正文不会被改写。
      </p>
      {state.digests.map((d) => (
        <div id={`digest-${d.id}`} key={d.id}>
          <DigestCard digest={d} onSource={onSource} />
        </div>
      ))}
    </>
  );
}
