import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, Lightbulb, PartyPopper } from 'lucide-react';
import { useEffect } from 'react';

interface FeedbackPanelProps {
  isCorrect: boolean;
  onNext: () => void;
  routeSummary?: string;
}

export function FeedbackPanel({ isCorrect, onNext, routeSummary }: FeedbackPanelProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onNext();
    }, 4500);
    
    return () => clearTimeout(timer);
  }, [onNext]);

  return (
    <AnimatePresence mode="wait">
      {isCorrect ? (
        <motion.div
          key="correct"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="rounded-[28px] bg-emerald-500 p-5 text-white shadow-xl shadow-emerald-200"
        >
          <div className="flex items-start gap-4">
            <motion.div
              animate={{ rotate: [0, 8, -8, 0] }}
              transition={{ repeat: Infinity, duration: 0.8 }}
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/20"
            >
              <PartyPopper className="h-8 w-8" />
            </motion.div>
            <div>
              <h2 className="mb-1 text-2xl font-black">太棒了，路线亮起来啦！</h2>
              <p className="text-base font-bold text-white/90">{routeSummary || '小列车已经顺利到站。'}</p>
            </div>
          </div>
          <button
            onClick={onNext}
            className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-white px-4 py-2 font-black text-emerald-600"
          >
            下一题
            <ArrowRight className="h-4 w-4" />
          </button>
        </motion.div>
      ) : (
        <motion.div
          key="wrong"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="rounded-[28px] bg-amber-500 p-5 text-white shadow-xl shadow-amber-200"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/20">
              <Lightbulb className="h-8 w-8" />
            </div>
            <div>
              <h2 className="mb-1 text-2xl font-black">差一点点，看看发光路线</h2>
              <p className="text-base font-bold text-white/90">{routeSummary || '先找同一条颜色的线路，再看哪里需要换乘。'}</p>
            </div>
          </div>
          <button
            onClick={onNext}
            className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-white px-4 py-2 font-black text-amber-600"
          >
            我知道啦
            <ArrowRight className="h-4 w-4" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
