import { useEffect, useState } from 'react';
import { useReflection } from '../hooks/useReflection';
import type { Reflection } from '../types';
import { format, parseISO } from 'date-fns';

export default function ReflectionPage() {
  const { loadReflectionLog, loadStats, stats } = useReflection();
  const [logs, setLogs] = useState<Reflection[]>([]);
  const [days, setDays] = useState(7);

  useEffect(() => {
    loadStats();
    loadLogs();
  }, [days]);

  const loadLogs = async () => {
    const data = await loadReflectionLog(days);
    setLogs(data);
  };

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
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">反省记录</h2>
        <div className="flex items-center gap-4">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="input w-32"
          >
            <option value={7}>最近7天</option>
            <option value={14}>最近14天</option>
            <option value={30}>最近30天</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="card p-4">
            <div className="text-2xl font-bold text-primary-600">{stats.totalReflections}</div>
            <div className="text-sm text-gray-500">总记录</div>
          </div>
          <div className="card p-4">
            <div className="text-2xl font-bold text-green-600">🔥{stats.currentStreak}</div>
            <div className="text-sm text-gray-500">连续天数</div>
          </div>
          <div className="card p-4">
            <div className="text-2xl font-bold text-accent-600">{Math.round(avgDeepWork)}</div>
            <div className="text-sm text-gray-500">日均深度工作</div>
          </div>
          <div className="card p-4">
            <div className="text-2xl font-bold text-orange-600">{Math.round(avgFamily)}</div>
            <div className="text-sm text-gray-500">日均家庭时间</div>
          </div>
          <div className="card p-4">
            <div className="text-2xl font-bold text-blue-600">{avgSleep.toFixed(1)}h</div>
            <div className="text-sm text-gray-500">平均睡眠</div>
          </div>
        </div>
      )}

      {/* Common Patterns */}
      {stats && stats.commonAvoidance.length > 0 && (
        <div className="card p-4 mb-6">
          <h3 className="font-medium text-gray-900 mb-3">常见的逃避模式</h3>
          <div className="flex flex-wrap gap-2">
            {stats.commonAvoidance.map((pattern, i) => (
              <span key={i} className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm">
                {pattern}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Log List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {logs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">🤔</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                还没有反省记录
              </h3>
              <p className="text-gray-500">
                开始记录你的每日反省吧
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {logs.map(log => (
              <div key={log.id} className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📅</span>
                    <span className="font-medium text-gray-900">
                      {format(parseISO(log.date), 'M月d日 EEEE')}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <span>⏱️ {log.deepWorkMin}min</span>
                    <span>👨‍👩‍👧 {log.familyMin}min</span>
                    <span>😴 {log.sleepH}h</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {log.keyWin && (
                    <div className="bg-green-50 rounded-lg p-3">
                      <div className="text-xs text-green-600 font-medium mb-1">🎉 收获</div>
                      <p className="text-sm text-gray-700">{log.keyWin}</p>
                    </div>
                  )}
                  {log.avoidance && (
                    <div className="bg-yellow-50 rounded-lg p-3">
                      <div className="text-xs text-yellow-600 font-medium mb-1">😰 逃避</div>
                      <p className="text-sm text-gray-700">{log.avoidance}</p>
                    </div>
                  )}
                </div>

                {log.nextFix && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className="text-xs text-primary-600 font-medium mb-1">🚀 明日目标</div>
                    <p className="text-sm text-gray-700">{log.nextFix}</p>
                  </div>
                )}

                {log.notes && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-sm text-gray-500 italic">{log.notes}</p>
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
