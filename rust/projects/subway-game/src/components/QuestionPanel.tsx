import { motion } from 'framer-motion';
import { Station } from '../types';

interface QuestionPanelProps {
  startStation: Station;
  endStation: Station;
}

export function QuestionPanel({ startStation, endStation }: QuestionPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-3xl shadow-lg p-6"
    >
      <div className="text-center">
        <div className="flex items-center justify-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-4xl">🚉</span>
            <div className="text-left">
              <div className="text-sm text-gray-500">起点</div>
              <div className="text-xl font-bold text-gray-800">
                {startStation.name}
              </div>
            </div>
          </div>
          
          <div className="text-3xl text-gray-400">→</div>
          
          <div className="flex items-center gap-2">
            <div className="text-left">
              <div className="text-sm text-gray-500">终点</div>
              <div className="text-xl font-bold text-gray-800">
                {endStation.name}
              </div>
            </div>
            <span className="text-4xl">🏁</span>
          </div>
        </div>
        
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="inline-block px-6 py-3 rounded-2xl bg-gradient-to-r from-primary to-secondary text-white font-bold text-lg"
        >
          🚇 小火车该怎么走呢？
        </motion.div>
      </div>
    </motion.div>
  );
}
