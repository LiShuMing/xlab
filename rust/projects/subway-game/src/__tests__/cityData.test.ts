import { describe, expect, it } from 'vitest';
import beijing from '../data/beijing.json';
import hangzhou from '../data/hangzhou.json';
import shanghai from '../data/shanghai.json';
import wuhan from '../data/wuhan.json';
import { CityData, DifficultyMode } from '../types';
import {
  generateQuestionOptions,
  generateRandomStationsByDifficulty
} from '../utils/routeCalculator';

const cityDatas = [beijing, hangzhou, wuhan, shanghai] as CityData[];
const difficulties: DifficultyMode[] = ['easy', 'medium', 'hard'];

describe('city subway data', () => {
  it.each(cityDatas)('%s has a connected playable network', cityData => {
    const stationIds = new Set(cityData.lines.flatMap(line => line.stations.map(station => station.id)));

    expect(cityData.lines.length).toBeGreaterThan(0);
    expect(stationIds.size).toBeGreaterThan(1);

    for (const difficulty of difficulties) {
      const question = generateRandomStationsByDifficulty(cityData, difficulty);
      const options = generateQuestionOptions(
        question.route,
        cityData.lines.flatMap(line => line.stations),
        cityData
      );

      expect(question.start.id).not.toBe(question.end.id);
      expect(question.route.stations[0].id).toBe(question.start.id);
      expect(question.route.stations[question.route.stations.length - 1].id).toBe(question.end.id);
      expect(options).toHaveLength(3);
    }
  });
});
