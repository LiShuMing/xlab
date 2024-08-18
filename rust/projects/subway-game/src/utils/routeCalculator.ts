import { Station, Line, Route, CityData } from '../types';

interface GraphNode {
  station: Station;
  lineId: string;
  neighbors: { station: Station; lineId: string }[];
}

// Build graph from city data
function buildGraph(cityData: CityData): Map<string, GraphNode> {
  const graph = new Map<string, GraphNode>();
  
  // Initialize all stations
  cityData.lines.forEach(line => {
    line.stations.forEach(station => {
      if (!graph.has(station.id)) {
        graph.set(station.id, {
          station,
          lineId: line.id,
          neighbors: []
        });
      }
    });
  });
  
  // Add edges (neighbors within same line)
  cityData.lines.forEach(line => {
    for (let i = 0; i < line.stations.length - 1; i++) {
      const current = line.stations[i];
      const next = line.stations[i + 1];
      
      const currentNode = graph.get(current.id);
      const nextNode = graph.get(next.id);
      
      if (currentNode && nextNode) {
        currentNode.neighbors.push({ station: next, lineId: line.id });
        nextNode.neighbors.push({ station: current, lineId: line.id });
      }
    }
  });
  
  return graph;
}

// BFS to find shortest route
export function findShortestRoute(
  startId: string,
  endId: string,
  cityData: CityData
): Route | null {
  const graph = buildGraph(cityData);
  
  if (!graph.has(startId) || !graph.has(endId)) {
    return null;
  }
  
  const queue: { 
    stationId: string; 
    path: Station[]; 
    lines: string[];
    transfers: number;
  }[] = [];
  const visited = new Map<string, number>(); // stationId -> min distance
  
  const startNode = graph.get(startId)!;
  queue.push({
    stationId: startId,
    path: [startNode.station],
    lines: [startNode.lineId],
    transfers: 0
  });
  visited.set(startId, 0);
  
  while (queue.length > 0) {
    const current = queue.shift()!;
    
    if (current.stationId === endId) {
      return {
        stations: current.path,
        lines: [...new Set(current.lines)],
        totalStops: current.path.length - 1,
        transferCount: current.transfers
      };
    }
    
    const currentNode = graph.get(current.stationId)!;
    
    for (const neighbor of currentNode.neighbors) {
      const neighborNode = graph.get(neighbor.station.id)!;
      const currentLine = current.lines[current.lines.length - 1];
      const newTransfers = currentLine !== neighbor.lineId ? current.transfers + 1 : current.transfers;
      
      if (!visited.has(neighbor.station.id) || 
          visited.get(neighbor.station.id)! > current.path.length) {
        visited.set(neighbor.station.id, current.path.length);
        
        queue.push({
          stationId: neighbor.station.id,
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
  const allStations: Station[] = [];
  cityData.lines.forEach(line => {
    allStations.push(...line.stations);
  });
  
  // Random shuffle and pick two different stations
  const shuffled = allStations.sort(() => Math.random() - 0.5);
  const start = shuffled[0];
  const end = shuffled[1] || shuffled[0];
  
  return { start, end: end.id !== start.id ? end : shuffled[2] || start };
}

// Shuffle array
function shuffleArray<T>(array: T[]): T[] {
  return array.sort(() => Math.random() - 0.5);
}

// Generate question options
export function generateQuestionOptions(
  correctRoute: Route,
  allStations: Station[],
  cityData: CityData
): Route[] {
  const options: Route[] = [correctRoute];
  
  // Generate 2 wrong options
  for (let i = 0; i < 2; i++) {
    const randomStations = generateRandomStations(cityData);
    const wrongRoute = findShortestRoute(randomStations.start.id, randomStations.end.id, cityData);
    
    if (wrongRoute && wrongRoute.stations.length > correctRoute.stations.length + 2) {
      options.push(wrongRoute);
    }
  }
  
  return shuffleArray(options);
}
