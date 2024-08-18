import { describe, it, expect } from 'vitest';
import { findShortestRoute, generateRandomStations } from '../utils/routeCalculator';
import { CityData } from '../types';

describe('RouteCalculator', () => {
  // Mock city data for testing
  const mockCityData: CityData = {
    cityId: 'test-city',
    cityName: 'Test City',
    lines: [
      {
        id: 'line-1',
        name: '1号线',
        color: '#FF0000',
        stations: [
          { id: 's1', name: '起点站', x: 0, y: 0 },
          { id: 's2', name: '中间站1', x: 100, y: 0 },
          { id: 's3', name: '中间站2', x: 200, y: 0 },
          { id: 's4', name: '终点站', x: 300, y: 0 },
        ],
      },
      {
        id: 'line-2',
        name: '2号线',
        color: '#00FF00',
        stations: [
          { id: 's2', name: '中间站1', x: 100, y: 0 },
          { id: 's5', name: '换乘站', x: 100, y: 100 },
          { id: 's6', name: '远端站', x: 100, y: 200 },
        ],
      },
    ],
  };

  describe('findShortestRoute', () => {
    it('should find route on same line', () => {
      const route = findShortestRoute('s1', 's3', mockCityData);
      
      expect(route).not.toBeNull();
      expect(route!.stations).toHaveLength(3);
      expect(route!.stations[0].id).toBe('s1');
      expect(route!.stations[2].id).toBe('s3');
      expect(route!.totalStops).toBe(2);
      expect(route!.transferCount).toBe(0);
    });

    it('should handle same start and end station', () => {
      const route = findShortestRoute('s1', 's1', mockCityData);
      
      expect(route).not.toBeNull();
      expect(route!.stations).toHaveLength(1);
      expect(route!.totalStops).toBe(0);
    });

    it('should handle non-existent stations', () => {
      const route = findShortestRoute('s1', 'nonexistent', mockCityData);
      
      expect(route).toBeNull();
    });

    it('should count transfers correctly', () => {
      const route = findShortestRoute('s1', 's5', mockCityData);
      
      expect(route).not.toBeNull();
      expect(route!.transferCount).toBe(1);
    });

    it('should return stations in order', () => {
      const route = findShortestRoute('s1', 's4', mockCityData);
      
      expect(route).not.toBeNull();
      const ids = route!.stations.map(s => s.id);
      expect(ids).toEqual(['s1', 's2', 's3', 's4']);
    });
  });

  describe('generateRandomStations', () => {
    it('should return different stations', () => {
      const result = generateRandomStations(mockCityData);
      
      expect(result.start.id).not.toBe(result.end.id);
    });

    it('should return stations from the city data', () => {
      const result = generateRandomStations(mockCityData);
      
      const allStationIds = mockCityData.lines.flatMap(l => l.stations).map(s => s.id);
      
      expect(allStationIds).toContain(result.start.id);
      expect(allStationIds).toContain(result.end.id);
    });

    it('should always have a valid start station', () => {
      for (let i = 0; i < 10; i++) {
        const result = generateRandomStations(mockCityData);
        expect(result.start.id).toBeDefined();
        expect(result.start.name).toBeDefined();
      }
    });
  });

  describe('Route Structure', () => {
    it('should include line IDs in route', () => {
      const route = findShortestRoute('s1', 's2', mockCityData);
      
      expect(route).not.toBeNull();
      expect(route!.lines).toBeDefined();
      expect(Array.isArray(route!.lines)).toBe(true);
    });

    it('should calculate correct total stops', () => {
      const route = findShortestRoute('s1', 's4', mockCityData);
      
      expect(route).not.toBeNull();
      expect(route!.totalStops).toBe(route!.stations.length - 1);
    });
  });
});
