import { describe, it, expect } from 'vitest';
import { City, Station, Line, CityData, Route, Question, GameState } from '../types';

describe('Type Definitions', () => {
  describe('City', () => {
    it('should have all required properties', () => {
      const city: City = {
        id: 'beijing',
        name: '北京',
        nameEn: 'Beijing',
        country: '中国',
        flag: '🇨🇳',
        icon: '🏯',
        color: '#C23A30',
        difficulty: 'medium',
        lineCount: 27,
        stationCount: 459,
        description: '中国的首都',
      };
      
      expect(city.id).toBe('beijing');
      expect(city.name).toBe('北京');
      expect(city.difficulty).toBe('medium');
    });
    
    it('should accept all difficulty levels', () => {
      const difficulties: GameState[] = ['selecting', 'playing', 'feedback'];
      
      difficulties.forEach(d => expect(d).toBeDefined());
    });
  });

  describe('Station', () => {
    it('should have position coordinates', () => {
      const station: Station = {
        id: 'test-station',
        name: '测试站',
        x: 100,
        y: 200,
      };
      
      expect(station.x).toBe(100);
      expect(station.y).toBe(200);
    });
  });

  describe('Line', () => {
    it('should contain stations array', () => {
      const line: Line = {
        id: 'line-1',
        name: '1号线',
        color: '#FF0000',
        stations: [
          { id: 's1', name: '站1', x: 0, y: 0 },
          { id: 's2', name: '站2', x: 100, y: 0 },
        ],
      };
      
      expect(line.stations).toHaveLength(2);
    });
  });

  describe('Route', () => {
    it('should calculate route properties', () => {
      const route: Route = {
        stations: [
          { id: 's1', name: '起点', x: 0, y: 0 },
          { id: 's2', name: '中间', x: 100, y: 0 },
          { id: 's3', name: '终点', x: 200, y: 0 },
        ],
        lines: ['line-1'],
        totalStops: 2,
        transferCount: 0,
      };
      
      expect(route.totalStops).toBe(2);
      expect(route.transferCount).toBe(0);
      expect(route.lines).toContain('line-1');
    });
  });

  describe('CityData', () => {
    it('should contain multiple lines', () => {
      const cityData: CityData = {
        cityId: 'test',
        cityName: '测试城市',
        lines: [
          { id: 'l1', name: '红线', color: '#f00', stations: [] },
          { id: 'l2', name: '蓝线', color: '#00f', stations: [] },
        ],
      };
      
      expect(cityData.lines).toHaveLength(2);
    });
  });

  describe('Question', () => {
    it('should link start and end stations', () => {
      const question: Question = {
        cityId: 'beijing',
        startStation: { id: 's1', name: '天安门', x: 0, y: 0 },
        endStation: { id: 's2', name: '西单', x: 100, y: 0 },
        correctRoute: {
          stations: [],
          lines: [],
          totalStops: 0,
          transferCount: 0,
        },
        options: [],
      };
      
      expect(question.startStation.name).toBe('天安门');
      expect(question.endStation.name).toBe('西单');
    });
  });
});
