import { motion, AnimatePresence } from 'framer-motion';
import { useEffect } from 'react';

interface FeedbackPanelProps {
  isCorrect: boolean;
  onNext: () => void;
}

export function FeedbackPanel({ isCorrect, onNext }: FeedbackPanelProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onNext();
    }, 2500);
    
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
          className="bg-gradient-to-r from-green-400 to-green-500 rounded-3xl shadow-lg p-6 text-center"
        >
          <motion.div
            animate={{ rotate: [0, 10, -10, 0] }}
            transition={{ repeat: Infinity, duration: 0.5 }}
            className="text-6xl mb-4"
          >
            🎉
          </motion.div>
          <h2 className="text-3xl font-bold text-white mb-2">
            太棒了！
          </h2>
          <p className="text-xl text-white">
            你已经是小向导啦！🌟
          </p>
        </motion.div>
      ) : (
        <motion.div
          key="wrong"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="bg-gradient-to-r from-orange-400 to-orange-500 rounded-3xl shadow-lg p-6 text-center"
        >
          <div className="text-6xl mb-4">🤔</div>
          <h2 className="text-3xl font-bold text-white mb-2">
            有点可惜
          </h2>
          <p className="text-xl text-white">
            再试试看！提示：看看颜色一样的线路～
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
