import { motion, AnimatePresence } from 'framer-motion';
import { CitySelector } from './components/CitySelector';
import { GameScreen } from './components/GameScreen';
import { useGameStore } from './stores/gameStore';

function App() {
  const { gameState } = useGameStore();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-4xl"
      >
        <AnimatePresence mode="wait">
          {gameState === 'selecting' && (
            <motion.div
              key="city-selector"
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 50 }}
            >
              <CitySelector />
            </motion.div>
          )}
          {(gameState === 'playing' || gameState === 'feedback') && (
            <motion.div
              key="game-screen"
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -50 }}
            >
              <GameScreen />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

export default App;
