export interface City {
  id: string;
  name: string;
  nameEn: string;
  country: string;
  flag: string;
  icon: string;
  color: string;
  difficulty: 'easy' | 'medium' | 'hard';
  lineCount: number;
  stationCount: number;
  description: string;
}

export interface Station {
  id: string;
  name: string;
  x: number;
  y: number;
}

export interface Line {
  id: string;
  name: string;
  color: string;
  stations: Station[];
}

export interface CityData {
  cityId: string;
  cityName: string;
  lines: Line[];
}

export interface Route {
  stations: Station[];
  lines: string[];
  totalStops: number;
  transferCount: number;
}

export interface Question {
  cityId: string;
  startStation: Station;
  endStation: Station;
  correctRoute: Route;
  options: Route[];
}

export type GameState = 'selecting' | 'playing' | 'feedback';

export interface GameProgress {
  cityId: string;
  correctCount: number;
  totalCount: number;
  lastPlayed: string;
}
