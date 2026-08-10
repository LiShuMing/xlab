import { BookOpen, CheckCircle2, ListChecks, PenLine, Plus, Save } from 'lucide-react';
import { useEffect, useState } from 'react';

export function InvestWorkspacePanel({
  stockCode,
  workspace,
  onSaveThesis,
  saving,
  busy,
  onCreateWatchItem,
  onUpdateWatchStatus,
  onCreateJournalEntry,
  onCreateReview,
}) {
  const thesis = workspace?.thesis;
  const watchItems = workspace?.watch_items ?? [];
  const journalEntries = workspace?.journal_entries ?? [];
  const reviews = workspace?.reviews ?? [];
  const [draft, setDraft] = useState(null);
  const [watchDraft, setWatchDraft] = useState({
    kind: 'manual',
    title: '',
    condition: '',
    priority: 5,
  });
  const [journalDraft, setJournalDraft] = useState({
    entry_type: 'note',
    action: '',
    price: '',
    reason: '',
    emotion: '',
  });
  const [reviewDraft, setReviewDraft] = useState({
    decision: 'no_action',
    thesis_valid: '',
    evidence_update: '',
    valuation_update: '',
    discipline_notes: '',
    next_action: '',
  });

  useEffect(() => {
    setDraft(thesis ? { ...thesis } : null);
  }, [thesis]);

  if (!stockCode) return null;

  if (!thesis || !draft) {
    return (
      <section className="invest-workspace-panel">
        <div className="invest-workspace-head">
          <BookOpen size={18} />
          <div>
            <span>Investment Thesis</span>
            <strong>{stockCode}</strong>
          </div>
        </div>
        <p className="invest-workspace-muted">生成报告后，这里会形成可编辑的长期投资假设卡。</p>
      </section>
    );
  }

  const updateDraft = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  const updateList = (key, index, value) => {
    const values = [...(draft[key] ?? [])];
    values[index] = value;
    updateDraft(key, values);
  };

  const submitWatch = (event) => {
    event.preventDefault();
    if (!watchDraft.title.trim()) return;
    onCreateWatchItem?.({
      ...watchDraft,
      title: watchDraft.title.trim(),
      condition: watchDraft.condition.trim(),
      priority: Number(watchDraft.priority) || 0,
    });
    setWatchDraft({ kind: 'manual', title: '', condition: '', priority: 5 });
  };

  const submitJournal = (event) => {
    event.preventDefault();
    if (!journalDraft.reason.trim() && !journalDraft.action.trim()) return;
    onCreateJournalEntry?.({
      ...journalDraft,
      price: journalDraft.price === '' ? null : Number(journalDraft.price),
      reason: journalDraft.reason.trim(),
      action: journalDraft.action.trim(),
      emotion: journalDraft.emotion.trim(),
    });
    setJournalDraft({ entry_type: 'note', action: '', price: '', reason: '', emotion: '' });
  };

  const submitReview = (event) => {
    event.preventDefault();
    if (!reviewDraft.next_action.trim() && !reviewDraft.evidence_update.trim()) return;
    onCreateReview?.({
      ...reviewDraft,
      thesis_valid: reviewDraft.thesis_valid === '' ? null : reviewDraft.thesis_valid === 'true',
      evidence_update: reviewDraft.evidence_update.trim(),
      valuation_update: reviewDraft.valuation_update.trim(),
      discipline_notes: reviewDraft.discipline_notes.trim(),
      next_action: reviewDraft.next_action.trim(),
    });
    setReviewDraft({
      decision: 'no_action',
      thesis_valid: '',
      evidence_update: '',
      valuation_update: '',
      discipline_notes: '',
      next_action: '',
    });
  };

  return (
    <section className="invest-workspace-panel">
      <div className="invest-workspace-head">
        <BookOpen size={18} />
        <div>
          <span>Investment Thesis</span>
          <strong>{draft.stock_code}</strong>
        </div>
        <button type="button" className="invest-icon-action" onClick={() => onSaveThesis?.(draft)} disabled={saving}>
          <Save size={16} />
        </button>
      </div>

      <div className="invest-thesis-grid">
        <label>
          状态
          <select value={draft.status} onChange={(event) => updateDraft('status', event.target.value)}>
            <option value="watchlist">观察</option>
            <option value="researching">深入研究</option>
            <option value="small_position">小仓位</option>
            <option value="holding">持有</option>
            <option value="trimming">减仓观察</option>
            <option value="exited">已退出</option>
          </select>
        </label>
        <label>
          信心
          <select value={draft.confidence} onChange={(event) => updateDraft('confidence', event.target.value)}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>
      </div>

      <label className="invest-thesis-field">
        核心投资假设
        <textarea value={draft.core_thesis} onChange={(event) => updateDraft('core_thesis', event.target.value)} rows={6} />
      </label>

      <label className="invest-thesis-field">
        安全边际
        <textarea value={draft.margin_of_safety} onChange={(event) => updateDraft('margin_of_safety', event.target.value)} rows={3} />
      </label>

      <EvidenceList title="支持证据" values={draft.supporting_evidence} onChange={(index, value) => updateList('supporting_evidence', index, value)} />
      <EvidenceList title="反方证据" values={draft.counter_evidence} onChange={(index, value) => updateList('counter_evidence', index, value)} />
      <EvidenceList
        title="证伪信号"
        values={draft.disconfirming_signals}
        onChange={(index, value) => updateList('disconfirming_signals', index, value)}
      />

      <div className="invest-workspace-columns">
        <WatchPanel
          items={watchItems}
          draft={watchDraft}
          setDraft={setWatchDraft}
          onSubmit={submitWatch}
          onUpdateStatus={onUpdateWatchStatus}
          busy={busy}
        />
        <JournalPanel
          entries={journalEntries}
          draft={journalDraft}
          setDraft={setJournalDraft}
          onSubmit={submitJournal}
          busy={busy}
        />
        <ReviewPanel
          reviews={reviews}
          draft={reviewDraft}
          setDraft={setReviewDraft}
          onSubmit={submitReview}
          busy={busy}
        />
      </div>
    </section>
  );
}

function EvidenceList({ title, values = [], onChange }) {
  const shown = values.length ? values : [''];
  return (
    <div className="invest-evidence-list">
      <span>{title}</span>
      {shown.map((item, index) => (
        <input key={`${title}-${index}`} value={item} onChange={(event) => onChange(index, event.target.value)} />
      ))}
    </div>
  );
}

function PanelHeader({ icon, title }) {
  return (
    <div className="invest-mini-head">
      {icon}
      <span>{title}</span>
    </div>
  );
}

function WatchPanel({ items, draft, setDraft, onSubmit, onUpdateStatus, busy }) {
  return (
    <div className="invest-mini-list">
      <PanelHeader icon={<ListChecks size={16} />} title="观察清单" />
      {items.length ? (
        <ul className="invest-watch-list">
          {items.slice(0, 5).map((item) => (
            <li key={item.id}>
              <span>{item.title}</span>
              <button
                type="button"
                className={item.status === 'done' ? 'done' : ''}
                disabled={busy}
                onClick={() => onUpdateStatus?.(item.id, item.status === 'done' ? 'open' : 'done')}
              >
                {item.status === 'done' ? 'done' : 'open'}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p>暂无观察项</p>
      )}
      <form className="invest-inline-form" onSubmit={onSubmit}>
        <input
          value={draft.title}
          onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
          placeholder="新增观察项"
        />
        <input
          value={draft.condition}
          onChange={(event) => setDraft((current) => ({ ...current, condition: event.target.value }))}
          placeholder="触发条件"
        />
        <button type="submit" disabled={busy || !draft.title.trim()}>
          <Plus size={14} />
        </button>
      </form>
    </div>
  );
}

function JournalPanel({ entries, draft, setDraft, onSubmit, busy }) {
  return (
    <div className="invest-mini-list">
      <PanelHeader icon={<PenLine size={16} />} title="投资日志" />
      {entries.length ? (
        <ul>
          {entries.slice(0, 4).map((item) => (
            <li key={item.id}>{item.reason || item.action || item.entry_type}</li>
          ))}
        </ul>
      ) : (
        <p>暂无日志</p>
      )}
      <form className="invest-inline-form" onSubmit={onSubmit}>
        <select
          value={draft.entry_type}
          onChange={(event) => setDraft((current) => ({ ...current, entry_type: event.target.value }))}
        >
          <option value="note">note</option>
          <option value="buy">buy</option>
          <option value="sell">sell</option>
          <option value="trim">trim</option>
        </select>
        <input
          value={draft.reason}
          onChange={(event) => setDraft((current) => ({ ...current, reason: event.target.value }))}
          placeholder="记录判断"
        />
        <input
          value={draft.price}
          onChange={(event) => setDraft((current) => ({ ...current, price: event.target.value }))}
          placeholder="价格"
          inputMode="decimal"
        />
        <button type="submit" disabled={busy || (!draft.reason.trim() && !draft.action.trim())}>
          <Plus size={14} />
        </button>
      </form>
    </div>
  );
}

function ReviewPanel({ reviews, draft, setDraft, onSubmit, busy }) {
  return (
    <div className="invest-mini-list">
      <PanelHeader icon={<CheckCircle2 size={16} />} title="复盘记录" />
      {reviews.length ? (
        <ul>
          {reviews.slice(0, 4).map((item) => (
            <li key={item.id}>{item.next_action || item.decision}</li>
          ))}
        </ul>
      ) : (
        <p>暂无复盘</p>
      )}
      <form className="invest-inline-form" onSubmit={onSubmit}>
        <select
          value={draft.decision}
          onChange={(event) => setDraft((current) => ({ ...current, decision: event.target.value }))}
        >
          <option value="no_action">no action</option>
          <option value="continue">continue</option>
          <option value="increase">increase</option>
          <option value="reduce">reduce</option>
          <option value="exit">exit</option>
        </select>
        <select
          value={draft.thesis_valid}
          onChange={(event) => setDraft((current) => ({ ...current, thesis_valid: event.target.value }))}
        >
          <option value="">unknown</option>
          <option value="true">valid</option>
          <option value="false">invalid</option>
        </select>
        <input
          value={draft.evidence_update}
          onChange={(event) => setDraft((current) => ({ ...current, evidence_update: event.target.value }))}
          placeholder="证据变化"
        />
        <input
          value={draft.next_action}
          onChange={(event) => setDraft((current) => ({ ...current, next_action: event.target.value }))}
          placeholder="下一步"
        />
        <button type="submit" disabled={busy || (!draft.next_action.trim() && !draft.evidence_update.trim())}>
          <Plus size={14} />
        </button>
      </form>
    </div>
  );
}
