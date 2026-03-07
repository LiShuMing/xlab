import { useState } from 'react';
import type { ReviewItem } from '../types';

interface FlashCardProps {
  item: ReviewItem;
  onAnswer: (score: number) => void;
  onSkip: () => void;
}

export default function FlashCard({ item, onAnswer, onSkip }: FlashCardProps) {
  const [isFlipped, setIsFlipped] = useState(false);

  const handleRate = (score: number) => {
    onAnswer(score);
    setIsFlipped(false);
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="card">
        {/* Card Content */}
        <div 
          onClick={() => setIsFlipped(!isFlipped)}
          className="p-8 cursor-pointer min-h-[200px] flex items-center justify-center"
        >
          <div className="text-center">
            <div className="text-xs text-gray-500 mb-4 uppercase tracking-wide">
              {item.type === 'vocab' ? '词汇' : '知识点'}
            </div>
            <div className="text-2xl font-medium text-gray-900 mb-4">
              {item.front}
            </div>
            
            {!isFlipped && (
              <p className="text-sm text-gray-400 animate-pulse">
                点击查看答案
              </p>
            )}
            
            {isFlipped && (
              <div className="mt-6 pt-6 border-t border-gray-100">
                <p className="text-lg text-gray-700 whitespace-pre-wrap">
                  {item.back}
                </p>
                {item.context && (
                  <p className="text-sm text-gray-500 mt-4 italic">
                    "{item.context}"
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        {isFlipped && (
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
            <p className="text-sm text-center text-gray-500 mb-3">
              你对这个知识点的掌握程度如何？
            </p>
            <div className="flex justify-center gap-2">
              <button
                onClick={() => handleRate(0)}
                className="px-3 py-2 rounded-lg bg-red-100 text-red-700 hover:bg-red-200 text-sm font-medium"
              >
                😓 忘了
              </button>
              <button
                onClick={() => handleRate(1)}
                className="px-3 py-2 rounded-lg bg-orange-100 text-orange-700 hover:bg-orange-200 text-sm font-medium"
              >
                😕 模糊
              </button>
              <button
                onClick={() => handleRate(2)}
                className="px-3 py-2 rounded-lg bg-yellow-100 text-yellow-700 hover:bg-yellow-200 text-sm font-medium"
              >
                😐 记得
              </button>
              <button
                onClick={() => handleRate(3)}
                className="px-3 py-2 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 text-sm font-medium"
              >
                🙂 熟悉
              </button>
              <button
                onClick={() => handleRate(4)}
                className="px-3 py-2 rounded-lg bg-green-100 text-green-700 hover:bg-green-200 text-sm font-medium"
              >
                😊 熟练
              </button>
              <button
                onClick={() => handleRate(5)}
                className="px-3 py-2 rounded-lg bg-emerald-100 text-emerald-700 hover:bg-emerald-200 text-sm font-medium"
              >
                🤩 精通
              </button>
            </div>
          </div>
        )}
      </div>

      {!isFlipped && (
        <div className="mt-4 text-center">
          <button
            onClick={onSkip}
            className="btn-ghost text-sm"
          >
            跳过这个问题
          </button>
        </div>
      )}
    </div>
  );
}
