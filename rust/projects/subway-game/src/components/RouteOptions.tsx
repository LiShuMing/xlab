import { motion } from 'framer-motion';
import { Route } from '../types';
import { useGameStore } from '../stores/gameStore';

// Cache for line colors from city data
let lineColorCache: Record<string, string> | null = null;

function getLineColorFromCache(lineId: string): string {
  return lineColorCache?.[lineId] || '#888';
}

export function setLineColors(colors: Record<string, string>) {
  lineColorCache = colors;
}

interface RouteOptionsProps {
  options: Route[];
  onSelect: (route: Route) => void;
  disabled: boolean;
}

export function RouteOptions({ options, onSelect, disabled }: RouteOptionsProps) {
  const { currentQuestion, selectedAnswer, isCorrect, cityData } = useGameStore();
  
  // Build line color cache from city data
  if (cityData && !lineColorCache) {
    const colors: Record<string, string> = {};
    cityData.lines.forEach(line => {
      colors[line.id] = line.color;
    });
    setLineColors(colors);
  }

  return (
    <div className="space-y-3">
      {options.map((route, index) => {
        const isSelected = selectedAnswer === route;
        const isAnswer = currentQuestion?.correctRoute === route;
        
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
              w-full p-4 rounded-2xl flex items-center gap-4
              border-4 transition-all
              ${isSelected && isAnswer
                ? 'border-success bg-green-50'
                : isSelected && !isAnswer
                  ? 'border-error bg-red-50'
                  : 'border-gray-200 bg-white hover:border-primary'
              }
              ${disabled ? 'cursor-default' : 'cursor-pointer'}
            `}
          >
            {/* Route visualization */}
            <div className="flex items-center gap-1">
              {route.lines.map((lineId, i) => (
                <div
                  key={i}
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                  style={{ 
                    backgroundColor: getLineColor(lineId),
                    zIndex: route.lines.length - i
                  }}
                >
                  {i + 1}
                </div>
              ))}
            </div>
            
            {/* Route info */}
            <div className="flex-1 text-left">
              <div className="font-bold text-gray-800">
                {route.stations[0].name} → {route.stations[route.stations.length - 1].name}
              </div>
              <div className="text-sm text-gray-500">
                {route.totalStops} 站
                {route.transferCount > 0 && ` · 换乘${route.transferCount}次`}
              </div>
            </div>
            
            {/* Result icon */}
            {isSelected && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
              >
                {isAnswer ? (
                  <span className="text-3xl">✅</span>
                ) : (
                  <span className="text-3xl">❌</span>
                )}
              </motion.div>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}

function getLineColor(lineId: string): string {
  return getLineColorFromCache(lineId);
}
