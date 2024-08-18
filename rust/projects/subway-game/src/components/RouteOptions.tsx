import { motion } from 'framer-motion';
import { CheckCircle2, CircleX, Route as RouteIcon, TrainFront } from 'lucide-react';
import { Route } from '../types';
import { useGameStore } from '../stores/gameStore';

interface RouteOptionsProps {
  options: Route[];
  onSelect: (route: Route) => void;
  disabled: boolean;
}

export function RouteOptions({ options, onSelect, disabled }: RouteOptionsProps) {
  const { currentQuestion, selectedAnswer, isCorrect, cityData } = useGameStore();
  const lineColors = new Map(cityData?.lines.map(line => [line.id, line.color]) || []);
  const lineNames = new Map(cityData?.lines.map(line => [line.id, line.name]) || []);

  return (
    <div className="space-y-3">
      {options.map((route, index) => {
        const isSelected = selectedAnswer === route;
        const isAnswer = currentQuestion?.correctRoute === route;
        const isCorrectSelection = isSelected && isAnswer;
        const isWrongSelection = isSelected && !isAnswer;
        
        return (
          <motion.button
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            whileHover={!disabled ? { scale: 1.02 } : {}}
            whileTap={!disabled ? { scale: 0.98 } : {}}
            onClick={() => !disabled && onSelect(route)}
            disabled={disabled}
            className={`
              group relative w-full overflow-hidden rounded-[24px] border p-4 text-left
              shadow-md transition-all
              ${isCorrectSelection
                ? 'border-emerald-300 bg-emerald-50 shadow-emerald-100'
                : isWrongSelection
                  ? 'border-rose-300 bg-rose-50 shadow-rose-100'
                  : 'border-white/80 bg-white/95 hover:border-rose-200 hover:shadow-lg'
              }
              ${disabled ? 'cursor-default' : 'cursor-pointer'}
            `}
          >
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white">
                <span className="text-xl font-black">{index + 1}</span>
              </div>

              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  {route.lines.map((lineId, i) => (
                    <span
                      key={`${lineId}-${i}`}
                      className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-black text-white"
                      style={{ backgroundColor: lineColors.get(lineId) || '#64748b' }}
                    >
                      <TrainFront className="h-4 w-4" />
                      {lineNames.get(lineId) || `线路${i + 1}`}
                    </span>
                  ))}
                </div>
                <div className="truncate text-lg font-black text-slate-800">
                  {route.stations[0].name} → {route.stations[route.stations.length - 1].name}
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm font-bold text-slate-500">
                  <RouteIcon className="h-4 w-4" />
                  {route.totalStops} 站
                  <span className="h-1 w-1 rounded-full bg-slate-300" />
                  {route.transferCount === 0 ? '不用换乘' : `换乘 ${route.transferCount} 次`}
                </div>
              </div>

              {isSelected && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="shrink-0"
                >
                  {isAnswer ? (
                    <CheckCircle2 className="h-9 w-9 fill-emerald-500 text-white" />
                  ) : (
                    <CircleX className="h-9 w-9 fill-rose-500 text-white" />
                  )}
                </motion.div>
              )}
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
