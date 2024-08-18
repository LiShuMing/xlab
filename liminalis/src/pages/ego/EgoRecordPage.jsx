import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { RecordCard } from '../../components/ego/RecordCard';
import { TerminalBlock } from '../../components/ego/TerminalBlock';
import { createRecord, listRecords } from '../../lib/ego/api';
import { generateRecordFeedback } from '../../lib/ego/aiFeedback';
import { todayLabel, greeting } from '../../lib/ego/date';
import { getCurrentRoleId, getRoleName } from '../../lib/ego/roles';
import { getAccountLabel } from '../../lib/ego/authState';
import { saveLocalRecord, listLocalRecords, getLocalRecord } from '../../lib/ego/localRecords';

export function EgoRecordPage() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [records, setRecords] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [loadState, setLoadState] = useState('loading');

  const roleId = getCurrentRoleId();
  const roleName = getRoleName(roleId);
  const accountLabel = getAccountLabel();

  const loadRecords = useCallback(async () => {
    setLoadState('loading');
    try {
      const data = await listRecords({ page: 1, size: 20, record_date: todayLabel() });
      setRecords(data.items || []);
      setLoadState('ready');
    } catch {
      setRecords(listLocalRecords());
      setLoadState('ready');
    }
  }, []);

  useEffect(() => { loadRecords(); }, [loadRecords]);

  async function handleSave() {
    const content = draft.trim();
    if (!content || saving) return;
    setSaving(true);

    const payload = { content_type: 'text', content };

    try {
      const record = await createRecord(payload);
      setRecords((prev) => [record, ...prev]);
    } catch {
      const localRec = saveLocalRecord({
        id: `local-${Date.now()}`,
        content_type: 'text',
        content,
        record_date: todayLabel(),
        created_at: new Date().toISOString(),
      });
      setRecords((prev) => [localRec, ...prev]);
    }

    // Client-side AI feedback
    setFeedback(generateRecordFeedback(content, roleId));
    setDraft('');
    setSaving(false);
  }

  function handleOpenRecord(record) {
    if (record.id && record.id.startsWith('local-')) {
      navigate(`/ego/record/${record.id}`);
    } else {
      navigate(`/ego/record/${record.id}`);
    }
  }

  return (
    <div className="ego2-page">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">{todayLabel()}</span>
          <span className="ego2-muted">{greeting()}</span>
        </div>
      </div>

      <div className="ego2-section">
        <textarea
          className="ego2-input-line"
          placeholder="写下今天的一个片段..."
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, 1000))}
          maxLength={1000}
        />
        <div className="ego2-char-count">{draft.length}/1000</div>
        <button className="ego2-btn" onClick={handleSave} disabled={!draft.trim() || saving}>
          {saving ? '保存中...' : '保存'}
        </button>
      </div>

      {feedback && (
        <div className="ego2-section">
          <TerminalBlock title={roleName} status="ai feedback">
            <div className="ego2-terminal-line">$ summarize: {feedback.summary}</div>
            <div className="ego2-terminal-line">$ respond: {feedback.response}</div>
            {feedback.prompts.map((p, i) => (
              <div key={i} className="ego2-terminal-line">$ follow_up: {p}</div>
            ))}
          </TerminalBlock>
        </div>
      )}

      <div className="ego2-section">
        <div className="ego2-split-actions">
          <button className="ego2-split-action" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            TEXT
          </button>
          <button className="ego2-split-action" onClick={() => { /* voice stub */ }}>
            VOICE
          </button>
          <button className="ego2-split-action" onClick={() => { /* photo stub */ }}>
            PHOTO
          </button>
        </div>
      </div>

      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">ACCOUNT</span>
          <span className="ego2-muted">{accountLabel} / {roleName}</span>
          <button className="ego2-link-btn" onClick={() => navigate('/ego/roles')}>切换角色</button>
        </div>
      </div>

      <div className="ego2-section">
        {loadState === 'loading' && <div className="ego2-status">加载记录中...</div>}
        {loadState === 'ready' && records.length === 0 && (
          <div className="ego2-status">今天还没有记录，写一条吧。</div>
        )}
        {records.map((rec) => (
          <RecordCard key={rec.id} record={rec} onOpen={handleOpenRecord} />
        ))}
      </div>
    </div>
  );
}
