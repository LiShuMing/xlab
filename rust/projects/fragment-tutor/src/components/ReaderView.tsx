import type { Document } from '../types';
import { useDocuments } from '../hooks/useDocuments';
import { getReadingTime } from '../utils/date';

interface ReaderViewProps {
  document: Document;
  onBack: () => void;
}

export default function ReaderView({ document, onBack }: ReaderViewProps) {
  const { currentAnalysis, isAnalyzing, analyzeDocument } = useDocuments();

  return (
    <div className="flex gap-6 h-full">
      {/* Main Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <button
          onClick={onBack}
          className="mb-4 btn-ghost text-sm"
        >
          ← 返回
        </button>

        <article className="card p-8 max-w-3xl">
          <header className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {document.title}
            </h1>
            {document.url && (
              <a 
                href={document.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-primary-600 hover:underline break-all"
              >
                {document.url}
              </a>
            )}
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span>{document.wordCount} 字</span>
              <span>{getReadingTime(document.wordCount)}</span>
              <span>{document.status}</span>
            </div>
          </header>

          <div className="prose prose-gray max-w-none">
            {document.content?.split('\n').map((para, i) => (
              <p key={i} className="mb-4 leading-relaxed">
                {para}
              </p>
            ))}
          </div>
        </article>
      </div>

      {/* Analysis Panel */}
      <div className="w-96 overflow-y-auto scrollbar-thin">
        <div className="sticky top-0">
          {document.status !== 'analyzed' && (
            <div className="card p-4 mb-4">
              <button
                onClick={() => analyzeDocument(document)}
                disabled={isAnalyzing}
                className="btn-primary w-full"
              >
                {isAnalyzing ? '分析中...' : 'AI 分析'}
              </button>
              <p className="text-xs text-gray-500 mt-2 text-center">
                使用 Claude 分析文章要点
              </p>
            </div>
          )}

          {currentAnalysis ? (
            <div className="space-y-4">
              {/* Thesis */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">核心论点</h3>
                <p className="text-sm text-gray-700">
                  {currentAnalysis.thesis}
                </p>
              </div>

              {/* First Principles */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">第一性原理</h3>
                <ul className="space-y-2">
                  {currentAnalysis.firstPrinciples.map((item, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-primary-500 mt-1">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Counterpoint */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">对立的观点</h3>
                <p className="text-sm text-gray-700">
                  {currentAnalysis.counterpoint}
                </p>
              </div>

              {/* Key Insights */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">关键洞见</h3>
                <ul className="space-y-2">
                  {currentAnalysis.keyInsights.map((item, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-accent-500 mt-1">💡</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Micro Actions */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">行动建议</h3>
                <ul className="space-y-2">
                  {currentAnalysis.microActions.map((item, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-green-500 mt-1">✓</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Vocabulary */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">词汇积累</h3>
                <div className="space-y-3">
                  {currentAnalysis.vocab.map((vocab, i) => (
                    <div key={i} className="border-b border-gray-100 last:border-0 pb-2 last:pb-0">
                      <div className="font-medium text-sm text-gray-900">
                        {vocab.word}
                        {vocab.pronunciation && (
                          <span className="text-gray-400 font-normal ml-2">
                            {vocab.pronunciation}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {vocab.definition}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Related Topics */}
              <div className="card p-4">
                <h3 className="font-medium text-gray-900 mb-2">相关主题</h3>
                <div className="flex flex-wrap gap-2">
                  {currentAnalysis.relatedTopics.map((topic, i) => (
                    <span key={i} className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : document.status === 'analyzed' ? (
            <div className="card p-8 text-center text-gray-500">
              <p>暂无分析结果</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
