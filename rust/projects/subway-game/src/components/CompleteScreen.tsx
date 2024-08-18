import { motion } from 'framer-motion';
import { Home, RotateCcw, Star, Trophy } from 'lucide-react';
import { useGameStore } from '../stores/gameStore';

export function CompleteScreen() {
  const {
    selectedCity,
    cityData,
    sessionCorrect,
    sessionLength,
    difficulty,
    goHome,
    selectCity
  } = useGameStore();
  const badge =
    sessionCorrect === sessionLength ? '满星站长' :
    sessionCorrect >= Math.ceil(sessionLength * 0.6) ? '勇敢向导' :
    '练习小车长';
  const note =
    sessionCorrect === sessionLength ? '每条路线都找到啦！' :
    sessionCorrect >= Math.ceil(sessionLength * 0.6) ? '已经能看懂不少路线了。' :
    '再玩一局，会越来越熟。';

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-3xl rounded-[36px] border border-white/80 bg-white/90 p-8 text-center shadow-2xl shadow-slate-200/80"
    >
      <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-[28px] bg-amber-400 text-white shadow-lg shadow-amber-200">
        <Trophy className="h-11 w-11" />
      </div>
      <div className="mb-2 text-sm font-black text-slate-400">
        {selectedCity?.name} · {difficulty === 'easy' ? '新手' : difficulty === 'medium' ? '小向导' : '挑战'}任务完成
      </div>
      <h1 className="mb-3 text-5xl font-black text-slate-800">{badge}</h1>
      <p className="mb-6 text-xl font-bold text-slate-500">{note}</p>

      <div className="mx-auto mb-7 grid max-w-md grid-cols-5 gap-2">
        {Array.from({ length: sessionLength }).map((_, index) => (
          <div
            key={index}
            className={`flex aspect-square items-center justify-center rounded-2xl ${
              index < sessionCorrect ? 'bg-amber-100 text-amber-500' : 'bg-slate-100 text-slate-300'
            }`}
          >
            <Star className={`h-7 w-7 ${index < sessionCorrect ? 'fill-amber-400' : ''}`} />
          </div>
        ))}
      </div>

      <div className="flex flex-col justify-center gap-3 sm:flex-row">
        <button
          onClick={() => cityData && selectCity(cityData.cityId)}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 font-black text-white shadow-md transition hover:-translate-y-0.5"
        >
          <RotateCcw className="h-5 w-5" />
          再玩一局
        </button>
        <button
          onClick={goHome}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white px-5 py-3 font-black text-slate-600 shadow-md transition hover:-translate-y-0.5"
        >
          <Home className="h-5 w-5" />
          换城市
        </button>
      </div>
    </motion.div>
  );
}
