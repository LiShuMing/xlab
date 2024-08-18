import { motion } from 'framer-motion';
import { Baby, Compass, Loader2, MapPinned, Play, Route, Sparkles, TrainFront, Trophy } from 'lucide-react';
import { useGameStore } from '../stores/gameStore';
import { DifficultyMode } from '../types';

const difficultyOptions: { id: DifficultyMode; label: string; note: string; icon: typeof Baby }[] = [
  { id: 'easy', label: '新手', note: '同线短路', icon: Baby },
  { id: 'medium', label: '小向导', note: '一次换乘', icon: Compass },
  { id: 'hard', label: '挑战', note: '认真观察', icon: Trophy }
];

export function CitySelector() {
  const { cities, selectCity, difficulty, selectDifficulty, isLoadingCity, loadError } = useGameStore();

  return (
    <div className="w-full">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto mb-8 max-w-3xl text-center"
      >
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/75 px-4 py-2 text-sm font-bold text-slate-600 shadow-sm backdrop-blur">
          <Sparkles className="h-4 w-4 text-amber-500" />
          小小站长任务台
        </div>
        <h1 className="mb-4 text-5xl font-black text-slate-800 md:text-6xl">
          地铁小向导
        </h1>
        <p className="mx-auto max-w-2xl text-xl font-semibold leading-8 text-slate-600">
          选一座城市，带着小列车找到正确路线。
        </p>
      </motion.div>

      <div className="mx-auto mb-6 grid max-w-3xl gap-3 sm:grid-cols-3">
        {difficultyOptions.map(option => {
          const Icon = option.icon;
          const active = difficulty === option.id;
          return (
            <button
              key={option.id}
              onClick={() => selectDifficulty(option.id)}
              className={`
                flex items-center gap-3 rounded-2xl border px-4 py-3 text-left shadow-sm transition
                ${active ? 'border-slate-900 bg-slate-900 text-white' : 'border-white/80 bg-white/80 text-slate-600 hover:bg-white'}
              `}
            >
              <span className={active ? 'text-white' : 'text-rose-500'}>
                <Icon className="h-6 w-6" />
              </span>
              <span>
                <span className="block text-base font-black">{option.label}</span>
                <span className={active ? 'text-xs font-bold text-white/70' : 'text-xs font-bold text-slate-400'}>
                  {option.note}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {cities.map((city, index) => (
          <motion.div
            key={city.id}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.1 }}
          >
            <motion.button
              whileHover={{ scale: 1.02, y: -4 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => selectCity(city.id)}
              disabled={isLoadingCity}
              className="
                group relative min-h-[220px] w-full overflow-hidden rounded-[28px]
                border border-white/80 bg-white/90 p-6 text-left shadow-xl shadow-slate-200/70
                transition-all hover:shadow-2xl disabled:cursor-wait disabled:opacity-70
              "
            >
              <div className="absolute inset-x-0 top-0 h-2" style={{ backgroundColor: city.color }} />
              <div className="absolute bottom-4 right-4 text-[92px] font-black leading-none text-slate-100 transition-transform group-hover:scale-110">
                {index + 1}
              </div>
              <div className="relative z-10 flex h-full flex-col justify-between gap-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl text-white shadow-lg" style={{ backgroundColor: city.color }}>
                    <TrainFront className="h-9 w-9" />
                  </div>
                  <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-500">
                    {city.country}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-3xl font-black text-slate-800">{city.name}</div>
                  <div className="flex flex-wrap gap-2 text-sm font-bold text-slate-500">
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1">
                      <Route className="h-4 w-4" />
                      {city.lineCount} 条线
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1">
                      <MapPinned className="h-4 w-4" />
                      {city.stationCount} 站
                    </span>
                  </div>
                </div>

                <div className="inline-flex w-fit items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-black text-white">
                  {isLoadingCity ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 fill-white" />
                  )}
                  {isLoadingCity ? '准备中' : '出发'}
                </div>
              </div>
            </motion.button>
          </motion.div>
        ))}
      </div>

      {loadError && (
        <div className="mx-auto mt-5 max-w-2xl rounded-2xl bg-amber-100 px-5 py-3 text-center text-sm font-black text-amber-700 shadow-sm">
          {loadError}
        </div>
      )}

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mx-auto mt-8 flex max-w-2xl items-center justify-center gap-3 rounded-full bg-white/70 px-5 py-3 text-center text-base font-bold text-slate-500 shadow-sm"
      >
        <TrainFront className="h-5 w-5 text-rose-500" />
        点一张城市车票，开始今天的小任务
      </motion.div>
    </div>
  );
}
