export function RecordCard({ record, onOpen }) {
  const timeLabel = record.created_at
    ? new Date(record.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <button type="button" className="ego2-record-card" onClick={() => onOpen(record)}>
      <div className="ego2-record-card__head">
        <span className="ego2-record-card__type">{record.content_type?.toUpperCase() || 'TEXT'}</span>
        {timeLabel && <span className="ego2-record-card__time">{timeLabel}</span>}
      </div>
      <div className="ego2-record-card__body">
        {record.content || <span className="ego2-record-card__empty">No content</span>}
      </div>
    </button>
  );
}
