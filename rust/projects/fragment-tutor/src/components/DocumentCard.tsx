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

  return (
    <div 
      onClick={onClick}
      className="card p-4 hover:shadow-md transition-shadow cursor-pointer group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">
              {document.type === 'url' ? '🔗' : '📝'}
            </span>
            <h3 className="font-medium text-gray-900 truncate">
              {document.title}
            </h3>
            <span className={statusColors[document.status as keyof typeof statusColors]}>
              {statusLabels[document.status as keyof typeof statusLabels]}
            </span>
          </div>

          {document.url && (
            <p className="text-sm text-gray-500 truncate mb-2">
              {document.url}
            </p>
          )}

          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{formatDate(document.capturedAt)}</span>
            <span>{document.wordCount} 字</span>
            <span>{getReadingTime(document.wordCount)}</span>
          </div>

          {document.topics.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {document.topics.slice(0, 5).map((topic, i) => (
                <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                  {topic}
                </span>
              ))}
            </div>
          )}
        </div>

        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="opacity-0 group-hover:opacity-100 p-2 text-gray-400 hover:text-red-500 transition-opacity"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
