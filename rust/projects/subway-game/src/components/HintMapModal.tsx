import { motion } from 'framer-motion';
import { Lightbulb, X } from 'lucide-react';
import { CityData, Question, Route } from '../types';
import { OfficialMetroMap } from './OfficialMetroMap';

interface HintMapModalProps {
  cityData: CityData;
  question: Question;
  highlightRoute: Route | null;
  onClose: () => void;
}

export function HintMapModal({
  cityData,
  question,
  highlightRoute,
  onClose
}: HintMapModalProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-5 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="地铁线路提示图"
    >
      <motion.div
        initial={{ scale: 0.94, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.94, y: 18 }}
        className="relative w-full max-w-6xl rounded-[34px] bg-white p-4 shadow-2xl"
      >
        <div className="mb-3 flex items-center justify-between gap-3 px-2">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-600">
              <Lightbulb className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-2xl font-black text-slate-800">高清提示图</div>
              <div className="truncate text-sm font-bold text-slate-500">
                已放大到 {question.startStation.name} → {question.endStation.name}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-600 shadow-sm transition hover:bg-slate-200"
            aria-label="关闭提示图"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <OfficialMetroMap
          cityData={cityData}
          startStation={question.startStation}
          endStation={question.endStation}
          highlightRoute={highlightRoute}
        />
      </motion.div>
    </motion.div>
  );
}
