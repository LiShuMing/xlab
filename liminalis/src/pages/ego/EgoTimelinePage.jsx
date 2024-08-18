import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTimeline } from '../../lib/ego/api';
import { currentMonth } from '../../lib/ego/date';

export function EgoTimelinePage() {
  const navigate = useNavigate();
  const [month, setMonth] = useState(currentMonth());
  const [days, setDays] = useState([]);
  const [loadState, setLoadState] = useState('idle');

  async function handleQuery() {
    if (!month) return;
    setLoadState('loading');
    try {
      const data = await getTimeline(month);
      setDays(data.days || []);
      setLoadState('ready');
    } catch {
      setDays([]);
      setLoadState('ready');
    }
  }

  function handleDayClick(day) {
    navigate(`/ego/record`);
  }

  return (
    <div className="ego2-page">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">TIMELINE</span>
          <h2 className="ego2-hero-title">时间线</h2>
        </div>
      </div>

      <div className="ego2-section">
        <div className="ego2-timeline-input">
          <input
            className="ego2-input-line"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
          <button className="ego2-btn" onClick={handleQuery}>查询</button>
        </div>
      </div>

      <div className="ego2-section">
        {loadState === 'loading' && <div className="ego2-status">加载中...</div>}
        {loadState === 'ready' && days.length === 0 && (
          <div className="ego2-status">该月没有记录</div>
        )}
        {days.map((day) => (
          <button
            key={day.date}
            className="ego2-timeline-day"
            onClick={() => handleDayClick(day)}
          >
            <span className="ego2-timeline-day__date">{day.date}</span>
            <span className="ego2-timeline-day__count">{day.count} 条</span>
            {day.preview && (
              <span className="ego2-timeline-day__preview">{day.preview}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
