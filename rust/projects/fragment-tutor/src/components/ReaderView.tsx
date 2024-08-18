import { ArrowLeft, Check, Circle, ExternalLink, Lightbulb, Loader2, Sparkles } from 'lucide-react';
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { useDocuments } from '../hooks/useDocuments';
import type { Document } from '../types';
import { getReadingTime } from '../utils/date';

interface ReaderViewProps {
  document: Document;
  onBack: () => void;
}

export default function ReaderView({ document, onBack }: ReaderViewProps) {
  const { currentAnalysis, isAnalyzing, analyzeDocument, loadAnalysis } = useDocuments();

  useEffect(() => {
    if (document.status === 'analyzed') {
      loadAnalysis(document.id);
    }
  }, [document.id, document.status, loadAnalysis]);

  return (
    <div className="flex h-full flex-col gap-6 xl:flex-row">
      <div className="min-w-0 flex-1 overflow-y-auto scrollbar-thin">
        <button onClick={onBack} className="btn-ghost mb-4 text-sm">
          <ArrowLeft className="h-4 w-4" />
          返回
        </button>

        <article className="max-w-3xl rounded-lg border border-slate-200 bg-white p-6 md:p-8">
          <header className="mb-6 border-b border-slate-200 pb-6">
            <h1 className="mb-3 text-2xl font-semibold leading-tight text-slate-950">
              {document.title}
            </h1>
            {document.url && (
              <a
                href={document.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex max-w-full items-center gap-2 truncate text-sm text-cyan-700 hover:text-cyan-800"
              >
                <ExternalLink className="h-4 w-4 shrink-0" />
                <span className="truncate">{document.url}</span>
              </a>
            )}
            <div className="mt-3 flex items-center gap-3 text-sm text-slate-500">
              <span>{document.wordCount} 字</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span>{getReadingTime(document.wordCount)}</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span>{document.status}</span>
            </div>
          </header>

          <div className="prose prose-slate max-w-none prose-p:my-3 prose-p:leading-8">
            {document.content?.split('\n').map((para, i) => (
              <p key={i} className="text-slate-700">
                {para}
              </p>
            ))}
          </div>
        </article>
      </div>

      <div className="w-full shrink-0 overflow-y-auto scrollbar-thin xl:w-96">
        <div className="sticky top-0">
          {document.status !== 'analyzed' && (
            <div className="panel mb-4 p-4">
              <button
                onClick={() => analyzeDocument(document)}
                disabled={isAnalyzing}
                className="btn-primary w-full"
              >
                {isAnalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {isAnalyzing ? '分析中' : 'AI 分析'}
              </button>
              <p className="mt-2 text-center text-xs text-slate-500">
                使用当前 LLM 配置生成摘要与复习卡片
              </p>
            </div>
          )}

          {currentAnalysis ? (
            <div className="space-y-4">
              <AnalysisBlock title="核心论点">
                <p className="text-sm leading-relaxed text-slate-700">{currentAnalysis.thesis}</p>
              </AnalysisBlock>

              <AnalysisBlock title="第一性原理">
                <List items={currentAnalysis.firstPrinciples} icon="circle" />
              </AnalysisBlock>

              <AnalysisBlock title="对立观点">
                <p className="text-sm leading-relaxed text-slate-700">{currentAnalysis.counterpoint}</p>
              </AnalysisBlock>

              <AnalysisBlock title="关键洞见">
                <List items={currentAnalysis.keyInsights} icon="lightbulb" />
              </AnalysisBlock>

              <AnalysisBlock title="行动建议">
                <List items={currentAnalysis.microActions} icon="check" />
              </AnalysisBlock>

              <AnalysisBlock title="词汇积累">
                <div className="space-y-3">
                  {currentAnalysis.vocab.map((vocab, i) => (
                    <div key={i} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                      <div className="text-sm font-medium text-slate-950">
                        {vocab.word}
                        {vocab.pronunciation && (
                          <span className="ml-2 font-normal text-slate-400">{vocab.pronunciation}</span>
                        )}
                      </div>
                      <div className="mt-1 text-xs leading-relaxed text-slate-600">{vocab.definition}</div>
                    </div>
                  ))}
                </div>
              </AnalysisBlock>

              <AnalysisBlock title="相关主题">
                <div className="flex flex-wrap gap-2">
                  {currentAnalysis.relatedTopics.map((topic, i) => (
                    <span key={i} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      {topic}
                    </span>
                  ))}
                </div>
              </AnalysisBlock>
            </div>
          ) : document.status === 'analyzed' ? (
            <div className="panel p-8 text-center text-slate-500">暂无分析结果</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function AnalysisBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-950">{title}</h3>
      {children}
    </section>
  );
}

function List({ items, icon }: { items: string[]; icon: 'circle' | 'lightbulb' | 'check' }) {
  const Icon = icon === 'lightbulb' ? Lightbulb : icon === 'check' ? Check : Circle;
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-slate-700">
          <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-700" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
