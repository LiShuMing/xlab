import { FileText, Link2, Loader2, X } from 'lucide-react';
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm animate-in">
      <div className="w-full max-w-lg overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl shadow-slate-950/10">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-950">捕获内容</h2>
            <p className="mt-0.5 text-xs text-slate-500">URL 与笔记会进入本地知识库</p>
          </div>
          <button
            onClick={() => setIsCaptureModalOpen(false)}
            className="icon-button"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="border-b border-slate-200 p-2">
          <div className="grid grid-cols-2 gap-2 rounded-md bg-slate-100 p-1">
            <button
              onClick={() => setActiveTab('url')}
              className={`btn h-8 ${activeTab === 'url' ? 'bg-white text-slate-950' : 'text-slate-500 hover:text-slate-950'}`}
            >
              <Link2 className="h-4 w-4" />
              捕获网址
            </button>
            <button
              onClick={() => setActiveTab('note')}
              className={`btn h-8 ${activeTab === 'note' ? 'bg-white text-slate-950' : 'text-slate-500 hover:text-slate-950'}`}
            >
              <FileText className="h-4 w-4" />
              手动记录
            </button>
          </div>
        </div>

        <div className="p-5">
          {activeTab === 'url' ? (
            <div>
              <label className="label">URL</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="input"
                autoFocus
              />
              <p className="mt-2 text-sm text-slate-500">
                捕获后会提取正文并保存到本地。
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
                  placeholder="想法或笔记标题"
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
                  className="input min-h-[132px] resize-y"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4">
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
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? '处理中' : '捕获'}
          </button>
        </div>
      </div>
    </div>
  );
}
