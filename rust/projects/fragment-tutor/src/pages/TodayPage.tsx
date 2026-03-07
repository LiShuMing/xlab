import { useEffect, useState } from 'react';
import { useReviews } from '../hooks/useReviews';
import { useReflection } from '../hooks/useReflection';
import { useDocuments } from '../hooks/useDocuments';
import FlashCard from '../components/FlashCard';
import { format } from 'date-fns';

export default function TodayPage() {
  const { reviewQueue, loadReviewQueue, submitReview } = useReviews();
  const { openReflection } = useReflection();
  const { documents, loadDocuments } = useDocuments();
  
  const [activeTab, setActiveTab] = useState<'review' | 'reading'>('review');
  const [currentReviewIndex, setCurrentReviewIndex] = useState(0);
  const [isReviewing, setIsReviewing] = useState(false);

  useEffect(() => {
    loadReviewQueue();
    loadDocuments();
  }, [loadReviewQueue, loadDocuments]);

  const dueReviews = reviewQueue.filter(item => !item.lastScore);
  const learningReviews = reviewQueue.filter(item => item.lastScore !== null);

  const handleReviewAnswer = async (score: number) => {
    const item = reviewQueue[currentReviewIndex];
    if (item) {
      await submitReview(item.id, score);
    }
  };

  const currentReviewItem = reviewQueue[currentReviewIndex];
  
  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">今日任务</h2>
        <p className="text-gray-500">{format(new Date(), 'EEEE, M月d日')}</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card p-4">
          <div className="text-2xl font-bold text-primary-600">{dueReviews.length}</div>
          <div className="text-sm text-gray-500">待复习</div>
        </div>
        <div className="card p-4">
          <div className="text-2xl font-bold text-green-600">{learningReviews.length}</div>
          <div className="text-sm text-gray-500">学习中</div>
        </div>
        <div className="card p-4">
          <div className="text-2xl font-bold text-accent-600">{documents.filter(d => d.status === 'analyzed').length}</div>
          <div className="text-sm text-gray-500">已分析</div>
        </div>
        <div className="card p-4 cursor-pointer hover:shadow-md transition-shadow" onClick={openReflection}>
          <div className="text-2xl font-bold text-orange-600">60s</div>
          <div className="text-sm text-gray-500">点击反省</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-4">
        <button
          onClick={() => setActiveTab('review')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'review'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          复习 ({reviewQueue.length})
        </button>
        <button
          onClick={() => setActiveTab('reading')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'reading'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          待阅读 ({documents.filter(d => d.status === 'captured').length})
        </button>
      </div>

      {/* Content */}
      {activeTab === 'review' ? (
        <div className="flex-1 flex flex-col">
          {reviewQueue.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4">🎉</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  复习完成！
                </h3>
                <p className="text-gray-500 mb-4">
                  今天没有待复习的内容了
                </p>
                <button onClick={openReflection} className="btn-primary">
                  进行今日反省
                </button>
              </div>
            </div>
          ) : isReviewing ? (
            <div className="flex-1 flex flex-col">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  {currentReviewIndex + 1} / {reviewQueue.length}
                </span>
                <button
                  onClick={() => setIsReviewing(false)}
                  className="btn-ghost text-sm"
                >
                  返回列表
                </button>
              </div>
              {currentReviewItem && (
                <FlashCard
                  item={currentReviewItem}
                  onAnswer={handleReviewAnswer}
                  onSkip={() => {
                    setCurrentReviewIndex(i => (i + 1) % reviewQueue.length);
                  }}
                />
              )}
              <div className="mt-4 flex justify-center gap-2">
                {reviewQueue.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setCurrentReviewIndex(i)}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      i === currentReviewIndex
                        ? 'bg-primary-500'
                        : i < currentReviewIndex
                        ? 'bg-green-500'
                        : 'bg-gray-300'
                    }`}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <div className="space-y-3">
                {reviewQueue.map((item, i) => (
                  <div
                    key={item.id}
                    onClick={() => {
                      setCurrentReviewIndex(i);
                      setIsReviewing(true);
                    }}
                    className="card p-4 cursor-pointer hover:shadow-md transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        item.type === 'vocab' ? 'bg-primary-100 text-primary-600' : 'bg-accent-100 text-accent-600'
                      }`}>
                        {item.type === 'vocab' ? '📖' : '💡'}
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{item.front}</div>
                        <div className="text-sm text-gray-500 truncate">{item.back}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-gray-500">
                          {item.lastScore !== null ? '学习中' : '新卡片'}
                        </div>
                        <div className="text-xs text-gray-400">
                          {item.streak} 天 streak
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setIsReviewing(true)}
                className="btn-primary w-full mt-4"
              >
                开始复习
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="space-y-3">
            {documents
              .filter(d => d.status === 'captured' || d.status === 'ingested')
              .map(doc => (
                <div
                  key={doc.id}
                  className="card p-4 cursor-pointer hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                      {doc.type === 'url' ? '🔗' : '📝'}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{doc.title}</div>
                      <div className="text-sm text-gray-500">
                        {doc.wordCount} 字 · {doc.status}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
          </div>
          {documents.filter(d => d.status === 'captured').length === 0 && (
            <div className="text-center py-12 text-gray-500">
              没有待阅读的内容
            </div>
          )}
        </div>
      )}
    </div>
  );
}
