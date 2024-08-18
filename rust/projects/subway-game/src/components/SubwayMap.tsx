import { motion } from 'framer-motion';
import { CityData, Station, Route } from '../types';

interface SubwayMapProps {
  cityData: CityData;
  startStation: Station;
  endStation: Station;
  highlightRoute: Route | null;
  focusMode?: 'overview' | 'question' | 'route';
  className?: string;
}

export function SubwayMap({
  cityData,
  startStation,
  endStation,
  highlightRoute,
  focusMode = 'overview',
  className = ''
}: SubwayMapProps) {
  const mapWidth = 600;
  const mapHeight = 500;
  const padding = 56;
  
  // Normalize coordinates
  const allStations = cityData.lines.flatMap(l => l.stations);
  const minX = Math.min(...allStations.map(s => s.x));
  const maxX = Math.max(...allStations.map(s => s.x));
  const minY = Math.min(...allStations.map(s => s.y));
  const maxY = Math.max(...allStations.map(s => s.y));
  
  const dataWidth = maxX - minX || 1;
  const dataHeight = maxY - minY || 1;
  const scaleX = (mapWidth - padding * 2) / dataWidth;
  const scaleY = (mapHeight - padding * 2) / dataHeight;
  const scale = Math.min(scaleX, scaleY) * 0.86;
  const offsetX = (mapWidth - dataWidth * scale) / 2;
  const offsetY = (mapHeight - dataHeight * scale) / 2;
  
  const getX = (x: number) => (x - minX) * scale + offsetX;
  const getY = (y: number) => mapHeight - ((y - minY) * scale + offsetY);
  const stationMembership = new Map<string, string[]>();
  cityData.lines.forEach(line => {
    line.stations.forEach(station => {
      const memberships = stationMembership.get(station.id) || [];
      if (!memberships.includes(line.id)) {
        stationMembership.set(station.id, [...memberships, line.id]);
      }
    });
  });
  const uniqueStations = Array.from(
    new Map(allStations.map(station => [station.id, station])).values()
  );
  const highlightedStationIds = new Set(highlightRoute?.stations.map(station => station.id) || []);
  const highlightedLineIds = new Set(highlightRoute?.lines || []);
  
  const isHighlighted = (station: Station) => {
    return highlightedStationIds.has(station.id);
  };
  
  const getStationStatus = (station: Station) => {
    if (station.id === startStation.id) return 'start';
    if (station.id === endStation.id) return 'end';
    if (isHighlighted(station)) return 'highlight';
    return 'normal';
  };
  const getLabelOffset = (station: Station) => {
    if (station.id === startStation.id) return -26;
    if (station.id === endStation.id) return -26;
    return -16;
  };
  const highlightPoints = highlightRoute?.stations.map(station => ({
    x: getX(station.x),
    y: getY(station.y)
  })) || [];
  const focusStations = focusMode === 'route' && highlightRoute
    ? highlightRoute.stations
    : [startStation, endStation];
  const focusPoints = focusStations.map(station => ({
    x: getX(station.x),
    y: getY(station.y)
  }));
  const focusMinX = Math.min(...focusPoints.map(point => point.x));
  const focusMaxX = Math.max(...focusPoints.map(point => point.x));
  const focusMinY = Math.min(...focusPoints.map(point => point.y));
  const focusMaxY = Math.max(...focusPoints.map(point => point.y));
  const focusPadding = focusMode === 'overview' ? 0 : 130;
  const focusViewBox = focusMode === 'overview'
    ? `0 0 ${mapWidth} ${mapHeight}`
    : [
        Math.max(0, focusMinX - focusPadding),
        Math.max(0, focusMinY - focusPadding),
        Math.min(mapWidth, focusMaxX + focusPadding) - Math.max(0, focusMinX - focusPadding),
        Math.min(mapHeight, focusMaxY + focusPadding) - Math.max(0, focusMinY - focusPadding)
      ].join(' ');

  return (
    <div className={`subway-map-board relative w-full aspect-[5/4] min-h-[430px] overflow-hidden rounded-[26px] ${className}`}>
      <div className="absolute left-4 top-4 z-10 rounded-2xl bg-white/90 px-4 py-3 shadow-lg">
        <div className="text-xs font-black text-slate-400">当前任务</div>
        <div className="mt-1 max-w-[230px] truncate text-lg font-black text-slate-800">
          {startStation.name} → {endStation.name}
        </div>
      </div>
      {highlightRoute && (
        <div className="absolute right-4 top-4 z-10 rounded-2xl bg-slate-900 px-4 py-3 text-white shadow-lg">
          <div className="text-xs font-black text-white/55">推荐路线</div>
          <div className="mt-1 text-base font-black">
            {highlightRoute.totalStops} 站 · {highlightRoute.transferCount === 0 ? '不用换乘' : `换乘 ${highlightRoute.transferCount} 次`}
          </div>
        </div>
      )}
      <svg
        viewBox={focusViewBox}
        className="w-full h-full"
      >
        <defs>
          <filter id="soft-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <pattern id="map-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#dbeafe" strokeWidth="1" opacity="0.65" />
          </pattern>
          <filter id="label-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#0f172a" floodOpacity="0.16" />
          </filter>
        </defs>
        <rect width={mapWidth} height={mapHeight} fill="url(#map-grid)" />
        <rect x="24" y="24" width={mapWidth - 48} height={mapHeight - 48} rx="30" fill="#ffffff" opacity="0.46" />

        {cityData.lines.map(line => (
          <g key={line.id}>
            <polyline
              points={line.stations.map(s => `${getX(s.x)},${getY(s.y)}`).join(' ')}
              fill="none"
              stroke="#ffffff"
              strokeWidth={highlightedLineIds.has(line.id) ? 18 : 14}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.9"
            />
            <motion.polyline
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1 }}
              points={line.stations.map(s => `${getX(s.x)},${getY(s.y)}`).join(' ')}
              fill="none"
              stroke={line.color}
              strokeWidth={highlightedLineIds.has(line.id) ? 9 : 7}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={highlightRoute && !highlightedLineIds.has(line.id) ? 0.32 : 0.92}
            />
            {line.stations.length > 1 && (
              <g filter="url(#label-shadow)">
                <rect
                  x={getX(line.stations[Math.floor(line.stations.length / 2)].x) - 28}
                  y={getY(line.stations[Math.floor(line.stations.length / 2)].y) + 12}
                  width="56"
                  height="22"
                  rx="11"
                  fill={line.color}
                  opacity={highlightRoute && !highlightedLineIds.has(line.id) ? 0.58 : 1}
                />
                <text
                  x={getX(line.stations[Math.floor(line.stations.length / 2)].x)}
                  y={getY(line.stations[Math.floor(line.stations.length / 2)].y) + 27}
                  textAnchor="middle"
                  className="fill-white text-[10px] font-black"
                >
                  {line.name}
                </text>
              </g>
            )}
          </g>
        ))}

        {highlightRoute && (
          <motion.polyline
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.65 }}
            points={highlightRoute.stations.map(s => `${getX(s.x)},${getY(s.y)}`).join(' ')}
            fill="none"
            stroke="#fde047"
            strokeWidth="18"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#soft-glow)"
          />
        )}

        {highlightPoints.length > 1 && (
          <motion.g
            animate={{
              x: highlightPoints.map(point => point.x),
              y: highlightPoints.map(point => point.y)
            }}
            transition={{
              duration: Math.max(2.4, highlightPoints.length * 0.75),
              repeat: Infinity,
              repeatDelay: 0.8,
              ease: 'easeInOut'
            }}
          >
            <circle r="12" fill="#0f172a" />
            <rect x="-10" y="-7" width="20" height="14" rx="5" fill="#ffffff" />
            <circle cx="-5" cy="8" r="2.5" fill="#0f172a" />
            <circle cx="5" cy="8" r="2.5" fill="#0f172a" />
          </motion.g>
        )}

        {uniqueStations.map((station, index) => {
            const status = getStationStatus(station);
            const isStart = status === 'start';
            const isEnd = status === 'end';
            const isHighlight = status === 'highlight';
            const isTransfer = (stationMembership.get(station.id)?.length || 0) > 1;
            const labelOffset = getLabelOffset(station);
            const shouldShowStationLabel = isStart || isEnd || (highlightRoute && isHighlight);
            
            return (
              <motion.g
                key={station.id}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: index * 0.02 }}
              >
                {(isStart || isEnd) && (
                  <g filter="url(#label-shadow)">
                    <rect
                      x={getX(station.x) - 42}
                      y={getY(station.y) + 18}
                      width="84"
                      height="28"
                      rx="14"
                      fill={isStart ? '#10b981' : '#f43f5e'}
                    />
                    <text
                      x={getX(station.x)}
                      y={getY(station.y) + 37}
                      textAnchor="middle"
                      className="fill-white text-[11px] font-black"
                    >
                      {isStart ? '起点' : '终点'}
                    </text>
                  </g>
                )}
                {isTransfer && (
                  <circle
                    cx={getX(station.x)}
                    cy={getY(station.y)}
                    r={highlightRoute && isHighlight ? 13 : 10}
                    fill="#ffffff"
                    stroke="#0f172a"
                    strokeWidth="2"
                    opacity={highlightRoute && !isHighlight ? 0.45 : 0.9}
                  />
                )}
                <circle
                  cx={getX(station.x)}
                  cy={getY(station.y)}
                  r={isStart || isEnd ? 13 : isHighlight ? 8 : isTransfer ? 5.5 : 4}
                  fill={
                    isStart ? '#10B981' :
                    isEnd ? '#F43F5E' :
                    isHighlight ? '#FACC15' :
                    'white'
                  }
                  stroke={isHighlight ? '#FACC15' : '#0f172a'}
                  strokeWidth={isHighlight || isStart || isEnd ? 4 : 1.8}
                  opacity={highlightRoute && !isHighlight && !isStart && !isEnd ? 0.55 : 1}
                  style={{
                    filter: isStart || isEnd ? 'drop-shadow(0 0 8px rgba(0,0,0,0.3))' : 'none'
                  }}
                />
                
                {shouldShowStationLabel ? (
                  <text
                    x={getX(station.x)}
                    y={getY(station.y) + labelOffset}
                    textAnchor="middle"
                    className="fill-slate-800 text-[11px] font-black"
                  >
                    {station.name}
                  </text>
                ) : null}
              </motion.g>
            );
          })}
      </svg>
      
      <div className="absolute bottom-3 left-3 rounded-2xl bg-white/90 p-3 text-xs font-black text-slate-600 shadow-md">
        <div className="mb-1 flex items-center gap-2">
          <span className="h-4 w-4 rounded-full bg-emerald-500"></span>
          <span>起点</span>
        </div>
        <div className="mb-1 flex items-center gap-2">
          <span className="h-4 w-4 rounded-full bg-rose-500"></span>
          <span>终点</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-4 w-4 rounded-full bg-yellow-400"></span>
          <span>路线</span>
        </div>
      </div>
    </div>
  );
}
