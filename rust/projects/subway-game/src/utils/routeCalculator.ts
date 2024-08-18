import { Station, Route, CityData, DifficultyMode } from '../types';

interface Graph {
  nodes: Map<string, GraphNode>;
  stationLines: Map<string, string[]>;
}

interface GraphNode {
  station: Station;
  neighbors: { station: Station; lineId: string }[];
}

// Build graph from city data
function buildGraph(cityData: CityData): Graph {
  const nodes = new Map<string, GraphNode>();
  const stationLines = new Map<string, string[]>();
  
  // Initialize all stations
  cityData.lines.forEach(line => {
    line.stations.forEach(station => {
      if (!nodes.has(station.id)) {
        nodes.set(station.id, {
          station,
          neighbors: []
        });
      }

      const lines = stationLines.get(station.id) || [];
      if (!lines.includes(line.id)) {
        stationLines.set(station.id, [...lines, line.id]);
      }
    });
  });
  
  // Add edges (neighbors within same line)
  cityData.lines.forEach(line => {
    for (let i = 0; i < line.stations.length - 1; i++) {
      const current = line.stations[i];
      const next = line.stations[i + 1];
      
      const currentNode = nodes.get(current.id);
      const nextNode = nodes.get(next.id);
      
      if (currentNode && nextNode) {
        currentNode.neighbors.push({ station: next, lineId: line.id });
        nextNode.neighbors.push({ station: current, lineId: line.id });
      }
    }
  });
  
  return { nodes, stationLines };
}

function compressLines(lines: string[]): string[] {
  return lines.filter((lineId, index) => index === 0 || lineId !== lines[index - 1]);
}

function createRoute(path: Station[], lines: string[], transfers: number): Route {
  return {
    stations: path,
    lines: compressLines(lines),
    totalStops: path.length - 1,
    transferCount: transfers
  };
}

function routeKey(route: Route): string {
  return [
    route.stations.map(station => station.id).join('>'),
    route.lines.join('>')
  ].join('|');
}

// BFS to find shortest route
export function findShortestRoute(
  startId: string,
  endId: string,
  cityData: CityData
): Route | null {
  const graph = buildGraph(cityData);
  
  if (!graph.nodes.has(startId) || !graph.nodes.has(endId)) {
    return null;
  }
  
  const queue: { 
    stationId: string; 
    lineId: string;
    path: Station[]; 
    lines: string[];
    transfers: number;
  }[] = [];
  const visited = new Map<string, { stops: number; transfers: number }>();
  
  const startNode = graph.nodes.get(startId)!;
  const startLines = graph.stationLines.get(startId) || [];
  startLines.forEach(lineId => {
    const stateKey = `${startId}:${lineId}`;
    queue.push({
      stationId: startId,
      lineId,
      path: [startNode.station],
      lines: [lineId],
      transfers: 0
    });
    visited.set(stateKey, { stops: 0, transfers: 0 });
  });
  
  while (queue.length > 0) {
    queue.sort((left, right) =>
      (left.path.length - right.path.length) || (left.transfers - right.transfers)
    );
    const current = queue.shift()!;
    
    if (current.stationId === endId) {
      return {
        stations: current.path,
        lines: [...new Set(current.lines)],
        totalStops: current.path.length - 1,
        transferCount: current.transfers
      };
    }
    
    const currentNode = graph.nodes.get(current.stationId)!;
    
    for (const neighbor of currentNode.neighbors) {
      const newTransfers = current.lineId !== neighbor.lineId ? current.transfers + 1 : current.transfers;
      const newStops = current.path.length;
      const stateKey = `${neighbor.station.id}:${neighbor.lineId}`;
      const previous = visited.get(stateKey);
      
      if (!previous || previous.stops > newStops ||
          (previous.stops === newStops && previous.transfers > newTransfers)) {
        visited.set(stateKey, { stops: newStops, transfers: newTransfers });
        
        queue.push({
          stationId: neighbor.station.id,
          lineId: neighbor.lineId,
          path: [...current.path, neighbor.station],
          lines: [...current.lines, neighbor.lineId],
          transfers: newTransfers
        });
      }
    }
  }
  
  return null;
}

// Generate random stations for a question
export function generateRandomStations(cityData: CityData): { start: Station; end: Station } {
  const stationMap = new Map<string, Station>();
  cityData.lines.forEach(line => line.stations.forEach(station => stationMap.set(station.id, station)));
  const allStations = Array.from(stationMap.values());
  if (allStations.length < 2) {
    throw new Error('At least two stations are required to generate a question.');
  }
  
  // Random shuffle and pick two different stations
  const shuffled = shuffleArray([...allStations]);
  const start = shuffled[0];
  const end = shuffled.find(station => station.id !== start.id)!;
  
  return { start, end };
}

function getUniqueStations(cityData: CityData): Station[] {
  const stationMap = new Map<string, Station>();
  cityData.lines.forEach(line => line.stations.forEach(station => stationMap.set(station.id, station)));
  return Array.from(stationMap.values());
}

function matchesDifficulty(route: Route, difficulty: DifficultyMode): boolean {
  if (route.totalStops < 1) return false;
  if (difficulty === 'easy') {
    return route.transferCount === 0 && route.totalStops <= 3;
  }
  if (difficulty === 'medium') {
    return route.transferCount <= 1 && route.totalStops <= 5;
  }
  return route.totalStops >= 3;
}

export function generateRandomStationsByDifficulty(
  cityData: CityData,
  difficulty: DifficultyMode
): { start: Station; end: Station; route: Route } {
  const stations = getUniqueStations(cityData);
  const shuffledStarts = shuffleArray(stations);
  const shuffledEnds = shuffleArray(stations);

  for (const start of shuffledStarts) {
    for (const end of shuffledEnds) {
      if (start.id === end.id) continue;
      const route = findShortestRoute(start.id, end.id, cityData);
      if (route && matchesDifficulty(route, difficulty)) {
        return { start, end, route };
      }
    }
  }

  const { start, end } = generateRandomStations(cityData);
  const route = findShortestRoute(start.id, end.id, cityData);
  if (!route) {
    throw new Error('Unable to generate a connected subway route.');
  }
  return { start, end, route };
}

// Shuffle array
function shuffleArray<T>(array: T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function findAlternativeRoutes(
  startId: string,
  endId: string,
  cityData: CityData,
  correctRoute: Route,
  maxRoutes = 6
): Route[] {
  const graph = buildGraph(cityData);
  if (!graph.nodes.has(startId) || !graph.nodes.has(endId)) {
    return [];
  }

  const startNode = graph.nodes.get(startId)!;
  const correctKey = routeKey(correctRoute);
  const maxStops = Math.max(correctRoute.totalStops + 6, correctRoute.totalStops * 2 + 2);
  const queue: {
    stationId: string;
    lineId: string;
    path: Station[];
    lines: string[];
    transfers: number;
    visitedStationIds: Set<string>;
  }[] = [];

  (graph.stationLines.get(startId) || []).forEach(lineId => {
    queue.push({
      stationId: startId,
      lineId,
      path: [startNode.station],
      lines: [lineId],
      transfers: 0,
      visitedStationIds: new Set([startId])
    });
  });

  const alternatives: Route[] = [];
  const seenRoutes = new Set<string>([correctKey]);
  let exploredStates = 0;
  const maxExploredStates = 1200;

  while (
    queue.length > 0 &&
    alternatives.length < maxRoutes &&
    exploredStates < maxExploredStates
  ) {
    const current = queue.shift()!;
    exploredStates += 1;
    if (current.path.length - 1 > maxStops) {
      continue;
    }

    if (current.stationId === endId && current.path.length > 1) {
      const route = createRoute(current.path, current.lines, current.transfers);
      const key = routeKey(route);
      if (!seenRoutes.has(key)) {
        alternatives.push(route);
        seenRoutes.add(key);
      }
      continue;
    }

    const currentNode = graph.nodes.get(current.stationId)!;
    for (const neighbor of currentNode.neighbors) {
      if (queue.length > maxExploredStates) {
        break;
      }
      if (current.visitedStationIds.has(neighbor.station.id)) {
        continue;
      }

      queue.push({
        stationId: neighbor.station.id,
        lineId: neighbor.lineId,
        path: [...current.path, neighbor.station],
        lines: [...current.lines, neighbor.lineId],
        transfers: current.lineId !== neighbor.lineId ? current.transfers + 1 : current.transfers,
        visitedStationIds: new Set([...current.visitedStationIds, neighbor.station.id])
      });
    }
  }

  return alternatives.sort((left, right) =>
    (left.totalStops - right.totalStops) || (left.transferCount - right.transferCount)
  );
}

function makeSyntheticDistractor(correctRoute: Route, stopOffset: number, transferOffset: number): Route {
  const lines = correctRoute.lines.length > 0 ? correctRoute.lines : ['unknown-line'];
  return {
    stations: correctRoute.stations,
    lines,
    totalStops: Math.max(1, correctRoute.totalStops + stopOffset),
    transferCount: Math.max(0, correctRoute.transferCount + transferOffset)
  };
}

// Generate question options
export function generateQuestionOptions(
  correctRoute: Route,
  _allStations: Station[],
  cityData: CityData
): Route[] {
  const startId = correctRoute.stations[0].id;
  const endId = correctRoute.stations[correctRoute.stations.length - 1].id;
  const alternatives = findAlternativeRoutes(startId, endId, cityData, correctRoute);
  const options: Route[] = [correctRoute, ...alternatives.slice(0, 2)];
  
  if (options.length < 3) {
    const fallbackCandidates = [
      makeSyntheticDistractor(correctRoute, 2, 0),
      makeSyntheticDistractor(correctRoute, 1, 1),
      makeSyntheticDistractor(correctRoute, 3, 1)
    ];
    for (const candidate of fallbackCandidates) {
      const duplicate = options.some(option =>
        option.totalStops === candidate.totalStops &&
        option.transferCount === candidate.transferCount &&
        option.lines.join('>') === candidate.lines.join('>')
      );
      if (!duplicate) {
        options.push(candidate);
      }
      if (options.length === 3) {
        break;
      }
    }
  }
  
  return shuffleArray(options.slice(0, 3));
}
