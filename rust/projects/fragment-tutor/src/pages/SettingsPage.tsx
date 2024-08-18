import { Command, Database, KeyRound, Save, Server, Target } from 'lucide-react';
import { useEffect, useState } from 'react';
import { settingsService } from '../services';
import { useStore } from '../store';
import type { RuntimeConfigStatus } from '../types';

export default function SettingsPage() {
  const { settings, setSettings, apiKey, setApiKey } = useStore();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeConfigStatus | null>(null);
  const [localSettings, setLocalSettings] = useState(settings);

  useEffect(() => {
    settingsService
      .getRuntimeConfigStatus()
      .then(setRuntimeStatus)
      .catch(() => setRuntimeStatus(null));
  }, []);

  const handleSaveApiKey = async () => {
    if (!apiKey || !apiKey.startsWith('sk-')) {
      setMessage({ type: 'error', text: '无效的 API key 格式' });
      return;
    }

    setSaving(true);
    try {
      const success = await settingsService.saveApiKey(apiKey);
      setMessage({ type: success ? 'success' : 'error', text: success ? 'API key 已保存' : '保存失败' });
    } catch {
      setMessage({ type: 'error', text: '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSettings = () => {
    setSettings(localSettings);
    setMessage({ type: 'success', text: '设置已保存' });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-slate-950">设置</h2>
        <p className="mt-1 text-sm text-slate-500">配置模型、目标与快捷键。</p>
      </div>

      <section className="panel mb-6 p-6">
        <SectionTitle icon={Server} title="LLM 配置" />

        <div className="space-y-4">
          {runtimeStatus && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <RuntimeTile icon={Server} label="模型" value={runtimeStatus.llmModel} />
              <RuntimeTile icon={KeyRound} label="服务" value={runtimeStatus.llmBaseUrl} truncate />
              <RuntimeTile
                icon={KeyRound}
                label="密钥状态"
                value={runtimeStatus.llmConfigured ? '已从环境读取' : '未配置'}
              />
              <RuntimeTile
                icon={Database}
                label="PSQL"
                value={
                  runtimeStatus.psqlConfigured
                    ? `${runtimeStatus.psqlHost}:${runtimeStatus.psqlPort}/${runtimeStatus.psqlDefaultDb}`
                    : '未配置'
                }
                truncate
              />
            </div>
          )}

          <div>
            <label className="label">临时覆盖 API Key</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={apiKey || ''}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="默认读取 ~/.env 的 LLM_API_KEY"
                className="input flex-1"
              />
              <button onClick={handleSaveApiKey} disabled={saving || !apiKey} className="btn-primary">
                <Save className="h-4 w-4" />
                {saving ? '保存中' : '保存'}
              </button>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              优先使用此处临时覆盖值；为空时使用 ~/.env 或进程环境中的 LLM_API_KEY。
            </p>
          </div>

          {message && (
            <div className={`rounded-md border p-3 text-sm ${
              message.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-rose-200 bg-rose-50 text-rose-700'
            }`}>
              {message.text}
            </div>
          )}
        </div>
      </section>

      <section className="panel mb-6 p-6">
        <SectionTitle icon={Target} title="每日目标" />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">复习卡片数</label>
            <input
              type="number"
              value={localSettings.dailyGoalReviews}
              onChange={(e) => setLocalSettings({
                ...localSettings,
                dailyGoalReviews: Number(e.target.value),
              })}
              min="1"
              max="100"
              className="input"
            />
          </div>
          <div>
            <label className="label">深度工作分钟</label>
            <input
              type="number"
              value={localSettings.dailyGoalDeepWorkMin}
              onChange={(e) => setLocalSettings({
                ...localSettings,
                dailyGoalDeepWorkMin: Number(e.target.value),
              })}
              min="0"
              max="480"
              className="input"
            />
          </div>
        </div>
      </section>

      <section className="panel mb-6 p-6">
        <SectionTitle icon={Command} title="快捷键" />
        <div className="space-y-3">
          <Shortcut label="打开反省卡片" value="Cmd/Ctrl + Shift + R" />
          <Shortcut label="打开捕获窗口" value="Cmd/Ctrl + Shift + N" />
        </div>
      </section>

      <div className="flex justify-end">
        <button onClick={handleSaveSettings} className="btn-primary">
          <Save className="h-4 w-4" />
          保存设置
        </button>
      </div>
    </div>
  );
}

function SectionTitle({ icon: Icon, title }: { icon: typeof Server; title: string }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <Icon className="h-4 w-4 text-cyan-700" />
      <h3 className="font-medium text-slate-950">{title}</h3>
    </div>
  );
}

function RuntimeTile({
  icon: Icon,
  label,
  value,
  truncate,
}: {
  icon: typeof Server;
  label: string;
  value: string;
  truncate?: boolean;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={`font-medium text-slate-950 ${truncate ? 'truncate' : ''}`}>{value}</div>
    </div>
  );
}

function Shortcut({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3">
      <span className="text-slate-700">{label}</span>
      <kbd className="rounded-md border border-slate-200 bg-white px-2 py-1 font-mono text-sm text-slate-600">
        {value}
      </kbd>
    </div>
  );
}
