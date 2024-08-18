import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TerminalBlock } from '../../components/ego/TerminalBlock';
import { getRecord, createRecord } from '../../lib/ego/api';
import { getLocalRecord, saveLocalRecord } from '../../lib/ego/localRecords';
import { todayLabel } from '../../lib/ego/date';

export function EgoRecordDetailPage() {
  const navigate = useNavigate();
  const { recordId } = useParams();
  const [content, setContent] = useState('');
  const [record, setRecord] = useState(null);
  const [loadState, setLoadState] = useState('loading');

  useEffect(() => {
    async function load() {
      if (!recordId || recordId.startsWith('local-')) {
        const local = recordId ? getLocalRecord(recordId) : null;
        if (local) {
          setRecord(local);
          setContent(local.content || '');
        }
        setLoadState(local ? 'ready' : 'missing');
        return;
      }

      try {
        const data = await getRecord(recordId);
        setRecord(data);
        setContent(data.content || '');
        setLoadState('ready');
      } catch {
        setLoadState('missing');
      }
    }
    load();
  }, [recordId]);

  async function handleSave() {
    if (!content.trim()) return;

    try {
      const payload = { content_type: record?.content_type || 'text', content };
      await createRecord(payload);
      navigate(-1);
    } catch {
      saveLocalRecord({
        id: recordId || `local-${Date.now()}`,
        content_type: 'text',
        content,
        record_date: todayLabel(),
        created_at: new Date().toISOString(),
      });
      navigate(-1);
    }
  }

  const mode = record?.content_type || 'text';

  return (
    <div className="ego2-page">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">{mode.toUpperCase()}</span>
          <button className="ego2-link-btn" onClick={() => navigate(-1)}>返回</button>
        </div>
      </div>

      {loadState === 'loading' && <div className="ego2-status">加载中...</div>}

      {loadState === 'missing' && (
        <div className="ego2-section">
          <TerminalBlock title="record" status="missing">
            <div>这条本地预览记录没有持久化副本</div>
          </TerminalBlock>
        </div>
      )}

      {loadState === 'ready' && (
        <div className="ego2-section">
          {mode === 'photo' && record?.media_url && (
            <img className="ego2-record-preview" src={record.media_url} alt="" />
          )}
          {mode === 'voice' && (
            <div className="ego2-status">语音录制待接入</div>
          )}
          <textarea
            className="ego2-input-line"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            maxLength={1000}
          />
          <div className="ego2-action-grid">
            <button className="ego2-btn" onClick={handleSave}>保存</button>
            <button className="ego2-btn ego2-btn--ghost" onClick={() => navigate(-1)}>返回</button>
          </div>
        </div>
      )}
    </div>
  );
}
