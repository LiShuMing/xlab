import { useEffect, useState } from 'react';
import { useReviews } from '../hooks/useReviews';
import FlashCard from '../components/FlashCard';

export default function ReviewPage() {
  const { reviewQueue, loadReviewQueue, submitReview } = useReviews();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showCompleted, setShowCompleted] = useState(false);

  useEffect(() => {
    loadReviewQueue();
  }, [loadReviewQueue]);

  const dueItems = reviewQueue.filter(item => !item.lastScore);
  const learningItems = reviewQueue.filter(item => item.lastScore !== null);
  const currentItem = reviewQueue[currentIndex];

  const handleAnswer = async (score: number) => {
    if (currentItem) {
      await submitReview(currentItem.id, score);
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

  // Group by type for stats
  const vocabCount = reviewQueue.filter(i => i.type === 'vocab').length;

  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">复习队列</h2>
        <p className="text-gray-500">间隔重复，巩固记忆</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card p-4">
          <div className="text-3xl font-bold text-primary-600">{reviewQueue.length}</div>
          <div className="text-sm text-gray-500">总卡片</div>
        </div>
        <div className="card p-4">
          <div className="text-3xl font-bold text-green-600">{dueItems.length}</div>
          <div className="text-sm text-gray-500">待学习</div>
        </div>
        <div className="card p-4">
          <div className="text-3xl font-bold text-accent-600">{learningItems.length}</div>
          <div className="text-sm text-gray-500">复习中</div>
        </div>
        <div className="card p-4">
          <div className="text-3xl font-bold text-orange-600">{vocabCount}</div>
          <div className="text-sm text-gray-500">词汇卡</div>
        </div>
      </div>

      {/* Progress */}
      {reviewQueue.length > 0 && (
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-500 mb-2">
            <span>复习进度</span>
            <span>{currentIndex + 1} / {reviewQueue.length}</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary-500 transition-all duration-300"
              style={{ width: `${((currentIndex + 1) / reviewQueue.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {reviewQueue.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">🧠</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                复习队列为空
              </h3>
              <p className="text-gray-500">
                捕获内容并分析后会生成复习卡片
              </p>
            </div>
          </div>
        ) : showCompleted ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">🎉</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                今日复习完成！
              </h3>
              <p className="text-gray-500 mb-4">
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
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-3">所有卡片</h3>
          <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto scrollbar-thin">
            {reviewQueue.map((item, i) => (
              <button
                key={item.id}
                onClick={() => setCurrentIndex(i)}
                className={`px-3 py-1 rounded-full text-sm transition-colors ${
                  i === currentIndex
                    ? 'bg-primary-100 text-primary-700'
                    : item.lastScore !== null
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
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
