import { motion } from 'framer-motion';
import { ArrowRight, Flag, MapPin, TrainFront } from 'lucide-react';
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
      className="overflow-hidden rounded-[30px] border border-white/80 bg-white/90 shadow-xl shadow-slate-200/70"
    >
      <div className="route-ticket px-5 py-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-black text-slate-500">
          <TrainFront className="h-5 w-5 text-rose-500" />
          今天的小列车任务
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
          <div className="rounded-2xl bg-emerald-50 p-4">
            <div className="mb-1 flex items-center gap-1 text-sm font-black text-emerald-600">
              <MapPin className="h-4 w-4" />
              起点
            </div>
            <div className="break-words text-2xl font-black text-slate-800">
              {startStation.name}
            </div>
          </div>
          
          <motion.div
            animate={{ x: [0, 4, 0] }}
            transition={{ repeat: Infinity, duration: 1.8 }}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-white"
          >
            <ArrowRight className="h-6 w-6" />
          </motion.div>
          
          <div className="rounded-2xl bg-rose-50 p-4">
            <div className="mb-1 flex items-center gap-1 text-sm font-black text-rose-600">
              <Flag className="h-4 w-4" />
              终点
            </div>
            <div className="break-words text-2xl font-black text-slate-800">
              {endStation.name}
            </div>
          </div>
        </div>
        
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="mt-4 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-base font-black text-white"
        >
          选一张正确路线票
        </motion.div>
      </div>
    </motion.div>
  );
}
