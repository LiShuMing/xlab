import { CalendarDays, Clock3, Moon, Target, Timer, Trophy } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { format, parseISO } from 'date-fns';
import { useReflection } from '../hooks/useReflection';
import type { Reflection } from '../types';

export default function ReflectionPage() {
  const { loadReflectionLog, loadStats, stats } = useReflection();
  const [logs, setLogs] = useState<Reflection[]>([]);
  const [days, setDays] = useState(7);

  const loadLogs = useCallback(async () => {
    const data = await loadReflectionLog(days);
    setLogs(data);
  }, [days, loadReflectionLog]);

  useEffect(() => {
    loadStats();
    loadLogs();
  }, [loadLogs, loadStats]);

  const avgDeepWork = logs.length > 0
    ? logs.reduce((sum, l) => sum + l.deepWorkMin, 0) / logs.length
    : 0;
  const avgFamily = logs.length > 0
    ? logs.reduce((sum, l) => sum + l.familyMin, 0) / logs.length
    : 0;
  const avgSleep = logs.length > 0
    ? logs.reduce((sum, l) => sum + l.sleepH, 0) / logs.length
    : 0;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">反省记录</h2>
          <p className="mt-1 text-sm text-slate-500">追踪每日反馈、行为模式与恢复质量。</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="input w-36"
        >
          <option value={7}>最近7天</option>
          <option value={14}>最近14天</option>
          <option value={30}>最近30天</option>
        </select>
      </div>

      {stats && (
        <div className="mb-6 grid grid-cols-5 gap-4">
          <Stat value={stats.totalReflections} label="总记录" tone="slate" />
          <Stat value={stats.currentStreak} label="连续天数" tone="emerald" />
          <Stat value={Math.round(avgDeepWork)} label="日均深度工作" tone="cyan" />
          <Stat value={Math.round(avgFamily)} label="日均家庭时间" tone="amber" />
          <Stat value={`${avgSleep.toFixed(1)}h`} label="平均睡眠" tone="indigo" />
        </div>
      )}

      {stats && stats.commonAvoidance.length > 0 && (
        <div className="panel mb-6 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-950">常见逃避模式</h3>
          <div className="flex flex-wrap gap-2">
            {stats.commonAvoidance.map((pattern, i) => (
              <span key={i} className="rounded-md bg-amber-50 px-3 py-1 text-sm text-amber-700">
                {pattern}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {logs.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="panel max-w-md p-8 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-slate-950 text-white">
                <CalendarDays className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-lg font-medium text-slate-950">还没有反省记录</h3>
              <p className="text-slate-500">开始记录你的每日反省吧</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {logs.map(log => (
              <div key={log.id} className="panel p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CalendarDays className="h-4 w-4 text-slate-500" />
                    <span className="font-medium text-slate-950">
                      {format(parseISO(log.date), 'M月d日 EEEE')}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-slate-500">
                    <span className="inline-flex items-center gap-1"><Timer className="h-4 w-4" />{log.deepWorkMin}min</span>
                    <span className="inline-flex items-center gap-1"><Clock3 className="h-4 w-4" />{log.familyMin}min</span>
                    <span className="inline-flex items-center gap-1"><Moon className="h-4 w-4" />{log.sleepH}h</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {log.keyWin && (
                    <div className="rounded-md border border-emerald-100 bg-emerald-50 p-3">
                      <div className="mb-1 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                        <Trophy className="h-3.5 w-3.5" />
                        收获
                      </div>
                      <p className="text-sm text-slate-700">{log.keyWin}</p>
                    </div>
                  )}
                  {log.avoidance && (
                    <div className="rounded-md border border-amber-100 bg-amber-50 p-3">
                      <div className="mb-1 text-xs font-medium text-amber-700">逃避</div>
                      <p className="text-sm text-slate-700">{log.avoidance}</p>
                    </div>
                  )}
                </div>

                {log.nextFix && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <div className="mb-1 inline-flex items-center gap-1.5 text-xs font-medium text-cyan-700">
                      <Target className="h-3.5 w-3.5" />
                      明日目标
                    </div>
                    <p className="text-sm text-slate-700">{log.nextFix}</p>
                  </div>
                )}

                {log.notes && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-sm text-slate-500">{log.notes}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  tone,
}: {
  value: number | string;
  label: string;
  tone: 'slate' | 'emerald' | 'cyan' | 'amber' | 'indigo';
}) {
  const colors = {
    slate: 'text-slate-950',
    emerald: 'text-emerald-700',
    cyan: 'text-cyan-700',
    amber: 'text-amber-700',
    indigo: 'text-indigo-700',
  };

  return (
    <div className="stat-card">
      <div className={`text-2xl font-semibold ${colors[tone]}`}>{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}
