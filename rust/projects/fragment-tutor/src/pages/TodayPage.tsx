import { BookOpen, CheckCircle2, FileText, Link2, RotateCw, ScanText, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import FlashCard from '../components/FlashCard';
import { useDocuments } from '../hooks/useDocuments';
import { useReflection } from '../hooks/useReflection';
import { useReviews } from '../hooks/useReviews';

export default function TodayPage() {
  const { reviewQueue, loadReviewQueue, submitReview, stats } = useReviews();
  const { openReflection } = useReflection();
  const { documents, loadDocuments } = useDocuments();

  const [activeTab, setActiveTab] = useState<'review' | 'reading'>('review');
  const [currentReviewIndex, setCurrentReviewIndex] = useState(0);
  const [isReviewing, setIsReviewing] = useState(false);

  useEffect(() => {
    loadReviewQueue();
    loadDocuments();
  }, [loadReviewQueue, loadDocuments]);

  const capturedDocs = documents.filter(d => d.status === 'captured' || d.status === 'ingested');
  const currentReviewItem = reviewQueue[currentReviewIndex];
  const recommendation = getRecommendation({
    dueCount: stats.dueCount,
    capturedCount: capturedDocs.length,
    analyzedCount: documents.filter(d => d.status === 'analyzed').length,
  });

  const handleReviewAnswer = async (score: number) => {
    const item = reviewQueue[currentReviewIndex];
    if (item) {
      await submitReview(item.id, score);
      setCurrentReviewIndex(i => {
        if (reviewQueue.length <= 1) {
          setIsReviewing(false);
          return 0;
        }
        return Math.min(i, reviewQueue.length - 2);
      });
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">今日任务</h2>
          <p className="mt-1 text-sm text-slate-500">{format(new Date(), 'EEEE, M月d日')}</p>
        </div>
        <button onClick={openReflection} className="btn-secondary">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          60秒反省
        </button>
      </div>

      <div className="mb-6 grid grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="text-2xl font-semibold text-cyan-700">{stats.dueCount}</div>
          <div className="text-sm text-slate-500">待复习</div>
        </div>
        <div className="stat-card">
          <div className="text-2xl font-semibold text-emerald-700">{stats.todayCompleted}</div>
          <div className="text-sm text-slate-500">今日完成</div>
        </div>
        <div className="stat-card">
          <div className="text-2xl font-semibold text-indigo-700">
            {documents.filter(d => d.status === 'analyzed').length}
          </div>
          <div className="text-sm text-slate-500">已分析</div>
        </div>
        <div className="stat-card">
          <div className="text-2xl font-semibold text-slate-950">{capturedDocs.length}</div>
          <div className="text-sm text-slate-500">待阅读</div>
        </div>
      </div>

      <div className="panel mb-6 flex items-center justify-between gap-4 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-950 text-white">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-950">下一步建议</div>
            <div className="text-sm text-slate-500">{recommendation.text}</div>
          </div>
        </div>
        <button
          onClick={() => {
            if (recommendation.tab) {
              setActiveTab(recommendation.tab);
            }
            if (recommendation.startReview) {
              setIsReviewing(true);
            }
          }}
          className="btn-secondary shrink-0"
        >
          {recommendation.action}
        </button>
      </div>

      <div className="mb-4 flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('review')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'review'
              ? 'border-slate-950 text-slate-950'
              : 'border-transparent text-slate-500 hover:text-slate-950'
          }`}
        >
          复习 ({reviewQueue.length})
        </button>
        <button
          onClick={() => setActiveTab('reading')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'reading'
              ? 'border-slate-950 text-slate-950'
              : 'border-transparent text-slate-500 hover:text-slate-950'
          }`}
        >
          待阅读 ({capturedDocs.length})
        </button>
      </div>

      {activeTab === 'review' ? (
        <div className="flex flex-1 flex-col">
          {reviewQueue.length === 0 ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="panel max-w-md p-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="mb-2 text-lg font-medium text-slate-950">复习完成</h3>
                <p className="mb-4 text-slate-500">今天没有待复习的内容了</p>
                <button onClick={openReflection} className="btn-primary">
                  进行今日反省
                </button>
              </div>
            </div>
          ) : isReviewing ? (
            <div className="flex flex-1 flex-col">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-sm text-slate-500">
                  {currentReviewIndex + 1} / {reviewQueue.length}
                </span>
                <button onClick={() => setIsReviewing(false)} className="btn-ghost text-sm">
                  返回列表
                </button>
              </div>
              {currentReviewItem && (
                <FlashCard
                  item={currentReviewItem}
                  onAnswer={handleReviewAnswer}
                  onSkip={() => setCurrentReviewIndex(i => (i + 1) % reviewQueue.length)}
                />
              )}
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <div className="space-y-3">
                {reviewQueue.map((item, i) => {
                  const Icon = item.type === 'vocab' ? BookOpen : ScanText;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setCurrentReviewIndex(i);
                        setIsReviewing(true);
                      }}
                      className="flex w-full items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 text-left transition-colors hover:border-cyan-300 hover:bg-cyan-50/30"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-600">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-slate-950">{item.front}</div>
                        <div className="truncate text-sm text-slate-500">{item.back}</div>
                      </div>
                      <div className="text-right text-xs text-slate-500">
                        <div>{item.lastScore !== null ? '学习中' : '新卡片'}</div>
                        <div>{item.streak} 天 streak</div>
                      </div>
                    </button>
                  );
                })}
              </div>
              <button onClick={() => setIsReviewing(true)} className="btn-primary mt-4 w-full">
                <RotateCw className="h-4 w-4" />
                开始复习
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="space-y-3">
            {capturedDocs.map(doc => {
              const Icon = doc.type === 'url' ? Link2 : FileText;
              return (
                <div key={doc.id} className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-600">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-slate-950">{doc.title}</div>
                    <div className="text-sm text-slate-500">
                      {doc.wordCount} 字 · {doc.status}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          {capturedDocs.length === 0 && (
            <div className="panel py-12 text-center text-slate-500">
              没有待阅读的内容
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function getRecommendation({
  dueCount,
  capturedCount,
  analyzedCount,
}: {
  dueCount: number;
  capturedCount: number;
  analyzedCount: number;
}): { text: string; action: string; tab?: 'review' | 'reading'; startReview?: boolean } {
  if (dueCount > 0) {
    return {
      text: `先完成 ${dueCount} 张到期卡片，保持记忆曲线不断档。`,
      action: '开始复习',
      tab: 'review',
      startReview: true,
    };
  }

  if (capturedCount > 0) {
    return {
      text: `还有 ${capturedCount} 条材料待阅读，适合用碎片时间清理。`,
      action: '查看待阅读',
      tab: 'reading',
    };
  }

  if (analyzedCount === 0) {
    return {
      text: '先捕获一篇材料并生成分析，让复习队列开始运转。',
      action: '查看知识库',
      tab: 'reading',
    };
  }

  return {
    text: '今日队列很干净，可以补一条反省或捕获新材料。',
    action: '保持节奏',
  };
}
