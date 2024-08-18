import { useState } from 'react';
import { useReflection } from '../hooks/useReflection';

export default function ReflectionCard() {
  const { closeReflection, saveReflection, loading, stats } = useReflection();
  
  const [keyWin, setKeyWin] = useState('');
  const [avoidance, setAvoidance] = useState('');
  const [nextFix, setNextFix] = useState('');
  const [deepWorkMin, setDeepWorkMin] = useState(120);
  const [familyMin, setFamilyMin] = useState(60);
  const [sleepH, setSleepH] = useState(7.0);
  const [notes, setNotes] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await saveReflection({
      keyWin,
      avoidance,
      nextFix,
      deepWorkMin,
      familyMin,
      sleepH,
      notes: notes || undefined,
    });
    closeReflection();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 sticky top-0 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">60秒反省</h2>
              <p className="text-sm text-gray-500">记录今日收获与改进</p>
            </div>
            <button
              onClick={closeReflection}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Stats */}
        {stats && stats.totalReflections > 0 && (
          <div className="px-6 py-3 bg-primary-50 border-b border-primary-100">
            <div className="flex items-center gap-6 text-sm">
              <span className="text-primary-700">
                🔥 连续 {stats.currentStreak} 天
              </span>
              <span className="text-primary-700">
                ⏱️ 平均深度工作 {Math.round(stats.avgDeepWorkMin)}分钟
              </span>
              <span className="text-primary-700">
                😴 平均睡眠 {stats.avgSleepH.toFixed(1)}小时
              </span>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Key Win */}
          <div>
            <label className="label">
              🎉 今日最重要的收获/成就
            </label>
            <textarea
              value={keyWin}
              onChange={(e) => setKeyWin(e.target.value)}
              placeholder="今天学到了什么？完成了什么？"
              className="input min-h-[80px] resize-y"
              required
            />
          </div>

          {/* Avoidance */}
          <div>
            <label className="label">
              😰 今天逃避了什么？
            </label>
            <textarea
              value={avoidance}
              onChange={(e) => setAvoidance(e.target.value)}
              placeholder="什么任务一直拖着没做？什么原因？"
              className="input min-h-[60px] resize-y"
              required
            />
          </div>

          {/* Next Fix */}
          <div>
            <label className="label">
              🚀 明天的第一要务
            </label>
            <input
              type="text"
              value={nextFix}
              onChange={(e) => setNextFix(e.target.value)}
              placeholder="明天最重要的一件事"
              className="input"
              required
            />
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">深度工作 (分钟)</label>
              <input
                type="number"
                value={deepWorkMin}
                onChange={(e) => setDeepWorkMin(Number(e.target.value))}
                min="0"
                max="480"
                className="input"
              />
            </div>
            <div>
              <label className="label">家庭时间 (分钟)</label>
              <input
                type="number"
                value={familyMin}
                onChange={(e) => setFamilyMin(Number(e.target.value))}
                min="0"
                max="480"
                className="input"
              />
            </div>
            <div>
              <label className="label">睡眠 (小时)</label>
              <input
                type="number"
                value={sleepH}
                onChange={(e) => setSleepH(Number(e.target.value))}
                min="0"
                max="24"
                step="0.5"
                className="input"
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="label">其他备注</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="其他想记录的..."
              className="input min-h-[60px] resize-y"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={closeReflection}
              className="btn-secondary"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading || !keyWin || !avoidance || !nextFix}
              className="btn-primary"
            >
              {loading ? '保存中...' : '保存反省记录'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
