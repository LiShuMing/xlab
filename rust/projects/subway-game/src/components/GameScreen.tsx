import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Eye, Home, Lightbulb, Map as MapIcon, Navigation, Star, TrainFront } from 'lucide-react';
import { useGameStore } from '../stores/gameStore';
import { QuestionPanel } from './QuestionPanel';
import { RouteOptions } from './RouteOptions';
import { FeedbackPanel } from './FeedbackPanel';
import { RouteGuide } from './RouteGuide';
import { HintMapModal } from './HintMapModal';

export function GameScreen() {
  const [showHintMap, setShowHintMap] = useState(false);
  const {
    selectedCity,
    cityData,
    currentQuestion,
    isCorrect,
    score,
    sessionQuestion,
    sessionLength,
    goHome,
    selectAnswer,
    nextQuestion
  } = useGameStore();
  const lineNames = new Map(cityData?.lines.map(line => [line.id, line.name]) || []);
  const routeSummary = currentQuestion
    ? `${currentQuestion.correctRoute.lines.map(lineId => lineNames.get(lineId) || lineId).join(' → ')}，共 ${currentQuestion.correctRoute.totalStops} 站`
    : undefined;

  return (
    <div className="w-full">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 grid grid-cols-[auto_1fr_auto] items-center gap-3"
      >
        <button
          onClick={goHome}
          className="flex h-12 items-center gap-2 rounded-2xl bg-white/90 px-4 font-black text-slate-600 shadow-md transition hover:-translate-y-0.5 hover:bg-white"
        >
          <Home className="h-5 w-5" />
          返回
        </button>
        
        <div className="mx-auto flex min-w-0 items-center gap-3 rounded-full bg-white/75 px-5 py-3 shadow-sm">
          <span className="flex h-10 w-10 items-center justify-center rounded-full text-white" style={{ backgroundColor: selectedCity?.color }}>
            <TrainFront className="h-6 w-6" />
          </span>
          <span className="truncate text-2xl font-black" style={{ color: selectedCity?.color }}>
            {selectedCity?.name}地铁
          </span>
        </div>
        
        <div className="flex h-12 items-center gap-2 rounded-2xl bg-white/90 px-4 font-black text-amber-500 shadow-md">
          <Star className="h-5 w-5 fill-amber-400" />
          {score}
        </div>
      </motion.div>

      <div className="mb-4 grid grid-cols-5 gap-2">
        {Array.from({ length: sessionLength }).map((_, index) => (
          <div
            key={index}
            className={`h-2 rounded-full ${index < sessionQuestion ? 'bg-rose-400' : 'bg-white/80'}`}
          />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(330px,0.86fr)_minmax(520px,1.14fr)]">
        <div className="space-y-4">
          {currentQuestion && (
            <>
              <QuestionPanel
                startStation={currentQuestion.startStation}
                endStation={currentQuestion.endStation}
              />
              
              <RouteOptions
                options={currentQuestion.options}
                onSelect={selectAnswer}
                disabled={isCorrect !== null}
              />
            </>
          )}
          
          {isCorrect !== null && (
            <>
              <FeedbackPanel
                isCorrect={isCorrect}
                onNext={nextQuestion}
                routeSummary={routeSummary}
              />
              {currentQuestion && cityData && (
                <RouteGuide route={currentQuestion.correctRoute} cityData={cityData} />
              )}
            </>
          )}
        </div>

        <div className="map-stage relative overflow-hidden rounded-[34px] border border-white/80 bg-white/90 p-6 shadow-2xl shadow-slate-200/80">
          <div className="flex h-full min-h-[430px] flex-col justify-between gap-8">
            <div>
              <div className="mb-5 flex items-center gap-3 text-lg font-black text-slate-700">
                <MapIcon className="h-5 w-5 text-teal-600" />
                小地图驾驶台
              </div>
              <div className="rounded-[28px] border-2 border-dashed border-teal-200 bg-gradient-to-br from-sky-50 via-white to-amber-50 p-6">
                <div className="flex items-start gap-4">
                  <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-teal-100 text-teal-700">
                    <Navigation className="h-8 w-8" />
                  </span>
                  <div>
                    <div className="text-2xl font-black text-slate-800">地图先藏起来</div>
                    <div className="mt-2 text-base font-bold leading-7 text-slate-500">
                      先试着用线路名称和站数判断路线；需要帮助时，再打开高清提示图。
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowHintMap(true)}
              disabled={!currentQuestion || !cityData}
              className="group flex w-full items-center justify-between rounded-[28px] bg-slate-900 px-6 py-5 text-left text-white shadow-xl transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="flex items-center gap-4">
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-300 text-slate-900">
                  <Lightbulb className="h-8 w-8" />
                </span>
                <span>
                  <span className="block text-2xl font-black">提示</span>
                  <span className="mt-1 block text-sm font-bold text-white/60">
                    {isCorrect === null ? '放大起点和终点，不直接公布答案' : '查看发光的正确路线'}
                  </span>
                </span>
              </span>
              <Eye className="h-7 w-7 text-white/70 transition group-hover:scale-110" />
            </button>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showHintMap && currentQuestion && cityData && (
          <HintMapModal
            cityData={cityData}
            question={currentQuestion}
            highlightRoute={isCorrect !== null ? currentQuestion.correctRoute : null}
            onClose={() => setShowHintMap(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
