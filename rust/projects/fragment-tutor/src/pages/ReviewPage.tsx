import { useEffect, useState } from 'react';
import { BrainCircuit, CheckCircle2 } from 'lucide-react';
import { useReviews } from '../hooks/useReviews';
import FlashCard from '../components/FlashCard';

export default function ReviewPage() {
  const { reviewQueue, loadReviewQueue, submitReview, stats } = useReviews();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showCompleted, setShowCompleted] = useState(false);

  useEffect(() => {
    loadReviewQueue();
  }, [loadReviewQueue]);

  const currentItem = reviewQueue[currentIndex];

  const handleAnswer = async (score: number) => {
    if (currentItem) {
      await submitReview(currentItem.id, score);
      handleNext();
    }
  };

  const handleNext = () => {
    setCurrentIndex(i => {
      const next = i + 1;
      if (next >= reviewQueue.length) {
        setShowCompleted(true);
        return 0;
      }
      return next;
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-slate-950">复习队列</h2>
        <p className="mt-1 text-sm text-slate-500">间隔重复，巩固记忆</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="stat-card">
          <div className="text-3xl font-semibold text-slate-950">{stats.totalCards}</div>
          <div className="text-sm text-slate-500">总卡片</div>
        </div>
        <div className="stat-card">
          <div className="text-3xl font-semibold text-cyan-700">{stats.dueCount}</div>
          <div className="text-sm text-slate-500">待学习</div>
        </div>
        <div className="stat-card">
          <div className="text-3xl font-semibold text-indigo-700">{stats.learningCount}</div>
          <div className="text-sm text-slate-500">复习中</div>
        </div>
        <div className="stat-card">
          <div className="text-3xl font-semibold text-emerald-700">{stats.todayCompleted}</div>
          <div className="text-sm text-slate-500">今日完成</div>
        </div>
      </div>

      {/* Progress */}
      {reviewQueue.length > 0 && (
        <div className="mb-6">
          <div className="mb-2 flex justify-between text-sm text-slate-500">
            <span>复习进度</span>
            <span>{currentIndex + 1} / {reviewQueue.length}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div 
              className="h-full bg-cyan-600 transition-all duration-300"
              style={{ width: `${((currentIndex + 1) / reviewQueue.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Main Content */}
        <div className="flex flex-1 flex-col">
        {reviewQueue.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="panel max-w-md p-8 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-slate-950 text-white">
                <BrainCircuit className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-lg font-medium text-slate-950">
                复习队列为空
              </h3>
              <p className="text-slate-500">
                捕获内容并分析后会生成复习卡片
              </p>
            </div>
          </div>
        ) : showCompleted ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="panel max-w-md p-8 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-lg font-medium text-slate-950">
                今日复习完成！
              </h3>
              <p className="mb-4 text-slate-500">
                你的记忆会感谢你的投入
              </p>
              <button
                onClick={() => {
                  setShowCompleted(false);
                  setCurrentIndex(0);
                  loadReviewQueue();
                }}
                className="btn-primary"
              >
                重新复习
              </button>
            </div>
          </div>
        ) : currentItem ? (
          <FlashCard
            item={currentItem}
            onAnswer={handleAnswer}
            onSkip={handleNext}
          />
        ) : null}
      </div>

      {/* Cards List */}
      {reviewQueue.length > 0 && !showCompleted && (
        <div className="mt-6 border-t border-slate-200 pt-4">
          <h3 className="mb-3 text-sm font-medium text-slate-700">所有卡片</h3>
          <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto scrollbar-thin">
            {reviewQueue.map((item, i) => (
              <button
                key={item.id}
                onClick={() => setCurrentIndex(i)}
                className={`px-3 py-1 rounded-full text-sm transition-colors ${
                  i === currentIndex
                    ? 'bg-slate-950 text-white'
                    : item.lastScore !== null
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {item.front.length > 20 ? item.front.slice(0, 20) + '...' : item.front}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
