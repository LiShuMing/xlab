import { motion } from 'framer-motion';
import { CityData, Station, Route } from '../types';

interface SubwayMapProps {
  cityData: CityData;
  startStation: Station;
  endStation: Station;
  highlightRoute: Route | null;
}

export function SubwayMap({ cityData, startStation, endStation, highlightRoute }: SubwayMapProps) {
  const mapWidth = 600;
  const mapHeight = 500;
  const padding = 50;
  
  // Normalize coordinates
  const allStations = cityData.lines.flatMap(l => l.stations);
  const minX = Math.min(...allStations.map(s => s.x));
  const maxX = Math.max(...allStations.map(s => s.x));
  const minY = Math.min(...allStations.map(s => s.y));
  const maxY = Math.max(...allStations.map(s => s.y));
  
  const scaleX = (mapWidth - padding * 2) / (maxX - minX || 1);
  const scaleY = (mapHeight - padding * 2) / (maxY - minY || 1);
  const scale = Math.min(scaleX, scaleY) * 0.8;
  
  const getX = (x: number) => (x - minX) * scale + padding;
  const getY = (y: number) => (mapHeight - (y - minY) * scale - padding);
  
  // Check if station is on highlight route
  const isHighlighted = (station: Station) => {
    if (!highlightRoute) return false;
    return highlightRoute.stations.some(s => s.id === station.id);
  };
  
  // Get station status
  const getStationStatus = (station: Station) => {
    if (station.id === startStation.id) return 'start';
    if (station.id === endStation.id) return 'end';
    if (isHighlighted(station)) return 'highlight';
    return 'normal';
  };

  return (
    <div className="relative w-full aspect-[4/3] bg-gray-50 rounded-2xl overflow-hidden">
      <svg
        viewBox={`0 0 ${mapWidth} ${mapHeight}`}
        className="w-full h-full"
      >
        {/* Draw lines */}
        {cityData.lines.map(line => (
          <g key={line.id}>
            {/* Line path */}
            <motion.polyline
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1 }}
              points={line.stations.map(s => `${getX(s.x)},${getY(s.y)}`).join(' ')}
              fill="none"
              stroke={line.color}
              strokeWidth="6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            
            {/* Highlighted route */}
            {highlightRoute && (
              <motion.polyline
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.5 }}
                points={highlightRoute.stations.map(s => `${getX(s.x)},${getY(s.y)}`).join(' ')}
                fill="none"
                stroke="#FFD700"
                strokeWidth="10"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: 'drop-shadow(0 0 8px #FFD700)' }}
              />
            )}
          </g>
        ))}
        
        {/* Draw stations */}
        {cityData.lines.map(line =>
          line.stations.map((station, index) => {
            const status = getStationStatus(station);
            const isStart = status === 'start';
            const isEnd = status === 'end';
            const isHighlight = status === 'highlight';
            
            return (
              <motion.g
                key={station.id}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: index * 0.02 }}
              >
                {/* Station circle */}
                <circle
                  cx={getX(station.x)}
                  cy={getY(station.y)}
                  r={isStart || isEnd ? 12 : isHighlight ? 8 : 6}
                  fill={
                    isStart ? '#4CAF50' :
                    isEnd ? '#F44336' :
                    isHighlight ? '#FFD700' :
                    'white'
                  }
                  stroke={isHighlight ? '#FFD700' : line.color}
                  strokeWidth={isHighlight ? 4 : 3}
                  style={{
                    filter: isStart || isEnd ? 'drop-shadow(0 0 8px rgba(0,0,0,0.3))' : 'none'
                  }}
                />
                
                {/* Station label */}
                {isStart || isEnd ? (
                  <text
                    x={getX(station.x)}
                    y={getY(station.y) - 20}
                    textAnchor="middle"
                    className="text-xs font-bold fill-gray-800"
                  >
                    {station.name}
                  </text>
                ) : null}
              </motion.g>
            );
          })
        )}
      </svg>
      
      {/* Legend */}
      <div className="absolute bottom-2 left-2 bg-white/90 rounded-xl p-2 text-xs">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-4 h-4 rounded-full bg-green-500"></span>
          <span>起点</span>
        </div>
        <div className="flex items-center gap-2 mb-1">
          <span className="w-4 h-4 rounded-full bg-red-500"></span>
          <span>终点</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 rounded-full bg-yellow-400"></span>
          <span>路线</span>
        </div>
      </div>
    </div>
  );
}
