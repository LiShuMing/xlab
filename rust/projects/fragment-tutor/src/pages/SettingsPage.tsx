import { useState } from 'react';
import { useStore } from '../store';
import { settingsService } from '../services';

export default function SettingsPage() {
  const { settings, setSettings, apiKey, setApiKey } = useStore();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [localSettings, setLocalSettings] = useState(settings);

  const handleSaveApiKey = async () => {
    if (!apiKey || !apiKey.startsWith('sk-')) {
      setMessage({ type: 'error', text: '无效的 API key 格式' });
      return;
    }
    
    setSaving(true);
    try {
      const success = await settingsService.saveApiKey(apiKey);
      if (success) {
        setMessage({ type: 'success', text: 'API key 已保存' });
      } else {
        setMessage({ type: 'error', text: '保存失败' });
      }
    } catch (e) {
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
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">设置</h2>
        <p className="text-gray-500">配置你的学习助手</p>
      </div>

      {/* API Key */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-gray-900 mb-4">🔑 Anthropic API</h3>
        
        <div className="space-y-4">
          <div>
            <label className="label">API Key</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={apiKey || ''}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-ant-api03-..."
                className="input flex-1"
              />
              <button
                onClick={handleSaveApiKey}
                disabled={saving || !apiKey}
                className="btn-primary"
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
            <p className="mt-2 text-sm text-gray-500">
              从 Anthropic Console 获取 API Key，用于 AI 分析功能
            </p>
          </div>

          {message && (
            <div className={`p-3 rounded-lg text-sm ${
              message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {message.text}
            </div>
          )}
        </div>
      </div>

      {/* Goals */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-gray-900 mb-4">🎯 每日目标</h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">复习卡片数</label>
            <input
              type="number"
              value={localSettings.dailyGoalReviews}
              onChange={(e) => setLocalSettings({
                ...localSettings,
                dailyGoalReviews: Number(e.target.value)
              })}
              min="1"
              max="100"
              className="input"
            />
          </div>
          <div>
            <label className="label">深度工作 (分钟)</label>
            <input
              type="number"
              value={localSettings.dailyGoalDeepWorkMin}
              onChange={(e) => setLocalSettings({
                ...localSettings,
                dailyGoalDeepWorkMin: Number(e.target.value)
              })}
              min="0"
              max="480"
              className="input"
            />
          </div>
        </div>
      </div>

      {/* Shortcuts */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-gray-900 mb-4">⌨️ 快捷键</h3>
        
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-gray-700">打开反省卡片</span>
            <kbd className="px-2 py-1 bg-white border border-gray-200 rounded text-sm font-mono">
              Cmd/Ctrl + Shift + R
            </kbd>
          </div>
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-gray-700">打开捕获窗口</span>
            <kbd className="px-2 py-1 bg-white border border-gray-200 rounded text-sm font-mono">
              Cmd/Ctrl + Shift + N
            </kbd>
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button
          onClick={handleSaveSettings}
          className="btn-primary"
        >
          保存设置
        </button>
      </div>
    </div>
  );
}
