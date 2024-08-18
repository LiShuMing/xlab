import { motion } from 'framer-motion';
import { useGameStore } from '../stores/gameStore';

export function CitySelector() {
  const { cities, selectCity } = useGameStore();

  return (
    <div className="w-full">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-8"
      >
        <h1 className="text-4xl font-bold text-gray-800 mb-2">
          🚇 地铁小向导
        </h1>
        <p className="text-xl text-gray-600">
          选择一个城市，开始地铁探险吧！
        </p>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
        {cities.map((city, index) => (
          <motion.div
            key={city.id}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.1 }}
          >
            <motion.button
              whileHover={{ scale: 1.05, y: -5 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => selectCity(city.id)}
              className="
                w-full aspect-square rounded-3xl
                flex flex-col items-center justify-center gap-3
                bg-white shadow-lg border-4
                cursor-pointer transition-all
                hover:shadow-xl
              "
              style={{ borderColor: city.color }}
            >
              <div 
                className="text-5xl"
                style={{ 
                  filter: 'drop-shadow(2px 2px 4px rgba(0,0,0,0.2))'
                }}
              >
                {city.icon}
              </div>
              <div className="text-2xl font-bold text-gray-800">
                {city.name}
              </div>
              <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-gray-100">
                <span className="text-sm">{city.flag}</span>
                <span className="text-sm text-gray-500">{city.country}</span>
              </div>
              <div className="text-sm text-gray-400">
                {city.stationCount} 站
              </div>
            </motion.button>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="text-center mt-8 text-gray-500"
      >
        <p className="text-lg">🎮 点击城市卡片开始游戏</p>
      </motion.div>
    </div>
  );
}
