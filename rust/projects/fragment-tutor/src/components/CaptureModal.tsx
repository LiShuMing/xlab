import { useState } from 'react';
import { useStore } from '../store';
import { useDocuments } from '../hooks/useDocuments';

export default function CaptureModal() {
  const { setIsCaptureModalOpen } = useStore();
  const { captureUrl, createNote, loading, error } = useDocuments();
  
  const [activeTab, setActiveTab] = useState<'url' | 'note'>('url');
  const [url, setUrl] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');

  const handleCapture = async () => {
    if (activeTab === 'url') {
      if (!url.trim()) return;
      await captureUrl(url.trim());
    } else {
      if (!noteTitle.trim() || !noteContent.trim()) return;
      await createNote(noteTitle.trim(), noteContent.trim());
    }
    setIsCaptureModalOpen(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">捕获内容</h2>
            <button
              onClick={() => setIsCaptureModalOpen(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('url')}
            className={`flex-1 px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'url'
                ? 'text-primary-600 border-b-2 border-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            捕获网址
          </button>
          <button
            onClick={() => setActiveTab('note')}
            className={`flex-1 px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'note'
                ? 'text-primary-600 border-b-2 border-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            手动记录
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {activeTab === 'url' ? (
            <div>
              <label className="label">网址 URL</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="input"
                autoFocus
              />
              <p className="mt-2 text-sm text-gray-500">
                捕获后将提取正文并保存，支持离线阅读
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="label">标题</label>
                <input
                  type="text"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  placeholder="想法/笔记标题"
                  className="input"
                  autoFocus
                />
              </div>
              <div>
                <label className="label">内容</label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="记录你的想法、灵感或笔记..."
                  className="input min-h-[120px] resize-y"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={() => setIsCaptureModalOpen(false)}
            className="btn-secondary"
          >
            取消
          </button>
          <button
            onClick={handleCapture}
            disabled={loading}
            className="btn-primary"
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                处理中...
              </>
            ) : (
              '捕获'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
