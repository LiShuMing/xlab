import { FileText, Link2, Trash2 } from 'lucide-react';
import type { Document } from '../types';
import { formatDate, getReadingTime } from '../utils/date';

interface DocumentCardProps {
  document: Document;
  onClick: () => void;
  onDelete?: () => void;
}

export default function DocumentCard({ document, onClick, onDelete }: DocumentCardProps) {
  const statusColors = {
    captured: 'badge-warning',
    ingested: 'badge-primary',
    analyzing: 'badge-primary',
    analyzed: 'badge-success',
    failed: 'badge-error',
  };

  const statusLabels = {
    captured: '已捕获',
    ingested: '处理中',
    analyzing: '分析中',
    analyzed: '已完成',
    failed: '失败',
  };

  const Icon = document.type === 'url' ? Link2 : FileText;

  return (
    <div
      onClick={onClick}
      className="group cursor-pointer rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-cyan-300 hover:bg-cyan-50/30"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-600">
            <Icon className="h-4 w-4" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="mb-2 flex items-center gap-2">
              <h3 className="truncate font-medium text-slate-950">
                {document.title}
              </h3>
              <span className={statusColors[document.status as keyof typeof statusColors]}>
                {statusLabels[document.status as keyof typeof statusLabels]}
              </span>
            </div>

            {document.url && (
              <p className="mb-2 truncate text-sm text-slate-500">
                {document.url}
              </p>
            )}

            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span>{formatDate(document.capturedAt)}</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span>{document.wordCount} 字</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span>{getReadingTime(document.wordCount)}</span>
            </div>

            {document.topics.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {document.topics.slice(0, 5).map((topic, i) => (
                  <span key={i} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {topic}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="icon-button opacity-0 group-hover:opacity-100"
            aria-label="删除文档"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
