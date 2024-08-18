import { Moon, Save, Timer, Trophy, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { FormEvent } from 'react';
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

  const handleSubmit = async (e: FormEvent) => {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm animate-in">
      <div className="mx-4 max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-2xl shadow-slate-950/10">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-950">60秒反省</h2>
            <p className="mt-0.5 text-sm text-slate-500">记录今日收获与改进</p>
          </div>
          <button onClick={closeReflection} className="icon-button" aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>

        {stats && stats.totalReflections > 0 && (
          <div className="grid grid-cols-3 gap-2 border-b border-slate-200 bg-slate-50 px-5 py-3 text-sm">
            <Metric icon={Trophy} label="连续" value={`${stats.currentStreak} 天`} />
            <Metric icon={Timer} label="深度工作" value={`${Math.round(stats.avgDeepWorkMin)} 分钟`} />
            <Metric icon={Moon} label="睡眠" value={`${stats.avgSleepH.toFixed(1)} 小时`} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5 p-5">
          <div>
            <label className="label">今日最重要的收获</label>
            <textarea
              value={keyWin}
              onChange={(e) => setKeyWin(e.target.value)}
              placeholder="今天学到了什么？完成了什么？"
              className="input min-h-[84px] resize-y"
              required
            />
          </div>

          <div>
            <label className="label">今天逃避了什么</label>
            <textarea
              value={avoidance}
              onChange={(e) => setAvoidance(e.target.value)}
              placeholder="什么任务一直拖着没做？原因是什么？"
              className="input min-h-[68px] resize-y"
              required
            />
          </div>

          <div>
            <label className="label">明天的第一要务</label>
            <input
              type="text"
              value={nextFix}
              onChange={(e) => setNextFix(e.target.value)}
              placeholder="明天最重要的一件事"
              className="input"
              required
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">深度工作</label>
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
              <label className="label">家庭时间</label>
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
              <label className="label">睡眠小时</label>
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

          <div>
            <label className="label">备注</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="其他想记录的..."
              className="input min-h-[64px] resize-y"
            />
          </div>

          <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
            <button type="button" onClick={closeReflection} className="btn-secondary">
              取消
            </button>
            <button
              type="submit"
              disabled={loading || !keyWin || !avoidance || !nextFix}
              className="btn-primary"
            >
              <Save className="h-4 w-4" />
              {loading ? '保存中' : '保存记录'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-2">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="text-sm font-medium text-slate-950">{value}</div>
    </div>
  );
}
