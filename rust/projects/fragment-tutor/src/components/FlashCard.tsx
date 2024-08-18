import { Eye, Lightbulb, RotateCw, Type } from 'lucide-react';
import { useState } from 'react';
import type { ReviewItem } from '../types';

interface FlashCardProps {
  item: ReviewItem;
  onAnswer: (score: number) => void;
  onSkip: () => void;
}

const ratings = [
  { score: 0, label: '忘记', className: 'border-rose-200 text-rose-700 hover:bg-rose-50' },
  { score: 2, label: '模糊', className: 'border-amber-200 text-amber-700 hover:bg-amber-50' },
  { score: 3, label: '记得', className: 'border-cyan-200 text-cyan-700 hover:bg-cyan-50' },
  { score: 4, label: '熟悉', className: 'border-emerald-200 text-emerald-700 hover:bg-emerald-50' },
  { score: 5, label: '精通', className: 'border-slate-300 text-slate-900 hover:bg-slate-50' },
];

export default function FlashCard({ item, onAnswer, onSkip }: FlashCardProps) {
  const [isFlipped, setIsFlipped] = useState(false);
  const Icon = item.type === 'vocab' ? Type : Lightbulb;

  const handleRate = (score: number) => {
    onAnswer(score);
    setIsFlipped(false);
  };

  return (
    <div className="mx-auto max-w-2xl">
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <button
          onClick={() => setIsFlipped(!isFlipped)}
          className="flex min-h-[260px] w-full items-center justify-center p-8 text-left"
        >
          <div className="w-full text-center">
            <div className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-700">
              <Icon className="h-5 w-5" />
            </div>
            <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {item.type === 'vocab' ? 'Vocabulary' : 'Insight'}
            </div>
            <div className="mx-auto max-w-lg text-2xl font-semibold leading-tight text-slate-950">
              {item.front}
            </div>

            {!isFlipped && (
              <div className="mt-6 inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-500">
                <Eye className="h-4 w-4" />
                点击查看答案
              </div>
            )}

            {isFlipped && (
              <div className="mx-auto mt-7 max-w-lg border-t border-slate-200 pt-6">
                <p className="whitespace-pre-wrap text-lg leading-relaxed text-slate-700">
                  {item.back}
                </p>
                {item.context && (
                  <p className="mt-4 rounded-md bg-slate-50 p-3 text-sm leading-relaxed text-slate-500">
                    {item.context}
                  </p>
                )}
              </div>
            )}
          </div>
        </button>

        {isFlipped && (
          <div className="border-t border-slate-200 bg-slate-50 px-5 py-4">
            <div className="flex flex-wrap justify-center gap-2">
              {ratings.map((rating) => (
                <button
                  key={rating.score}
                  onClick={() => handleRate(rating.score)}
                  className={`rounded-md border bg-white px-3 py-2 text-sm font-medium transition-colors ${rating.className}`}
                >
                  {rating.label}
                </button>
              ))}
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
            <RotateCw className="h-4 w-4" />
            跳过
          </button>
        </div>
      )}
    </div>
  );
}
