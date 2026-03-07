import { motion } from 'framer-motion';
import { useGameStore } from '../stores/gameStore';
import { QuestionPanel } from './QuestionPanel';
import { RouteOptions } from './RouteOptions';
import { FeedbackPanel } from './FeedbackPanel';
import { SubwayMap } from './SubwayMap';

export function GameScreen() {
  const { selectedCity, currentQuestion, isCorrect, gameState } = useGameStore();

  return (
    <div className="w-full max-w-5xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-6"
      >
        <button
          onClick={() => useGameStore.getState().goHome()}
          className="px-4 py-2 rounded-xl bg-white shadow-md text-gray-700 font-bold hover:bg-gray-50"
        >
          ← 返回
        </button>
        
        <div className="flex items-center gap-3">
          <span className="text-3xl">{selectedCity?.icon}</span>
          <span className="text-2xl font-bold" style={{ color: selectedCity?.color }}>
            {selectedCity?.name}地铁
          </span>
        </div>
        
        <div className="px-4 py-2 rounded-xl bg-white shadow-md">
          <span className="text-lg font-bold text-primary">
            ⭐ {useGameStore.getState().score}
          </span>
        </div>
      </motion.div>

      {/* Main Game Area */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Left: Question & Options */}
        <div className="space-y-4">
          {currentQuestion && (
            <>
              <QuestionPanel
                startStation={currentQuestion.startStation}
                endStation={currentQuestion.endStation}
              />
              
              <RouteOptions
                options={currentQuestion.options}
                onSelect={(route) => useGameStore.getState().selectAnswer(route)}
                disabled={isCorrect !== null}
              />
            </>
          )}
          
          {isCorrect !== null && (
            <FeedbackPanel
              isCorrect={isCorrect}
              onNext={() => useGameStore.getState().nextQuestion()}
            />
          )}
        </div>

        {/* Right: Map */}
        <div className="bg-white rounded-3xl shadow-lg p-4">
          {currentQuestion && (
            <SubwayMap
              cityData={useGameStore.getState().cityData!}
              startStation={currentQuestion.startStation}
              endStation={currentQuestion.endStation}
              highlightRoute={
                isCorrect !== null
                  ? currentQuestion.correctRoute
                  : null
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
