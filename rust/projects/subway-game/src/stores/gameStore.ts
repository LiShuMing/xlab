import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { City, CityData, Question, GameState, GameProgress, Route } from '../types';
import { findShortestRoute, generateRandomStations, generateQuestionOptions } from '../utils/routeCalculator';
import { setLineColors } from '../components/RouteOptions';
import citiesData from '../data/cities.json';

// Type assertion for cities data
const cities: City[] = citiesData.cities.map(city => ({
  ...city,
  difficulty: city.difficulty as 'easy' | 'medium' | 'hard'
}));

interface GameStore {
  // State
  gameState: GameState;
  cities: City[];
  selectedCity: City | null;
  cityData: CityData | null;
  currentQuestion: Question | null;
  selectedAnswer: Route | null;
  isCorrect: boolean | null;
  score: number;
  totalQuestions: number;
  progress: Record<string, GameProgress>;
  
  // Actions
  selectCity: (cityId: string) => Promise<void>;
  generateQuestion: () => void;
  selectAnswer: (route: Route) => void;
  nextQuestion: () => void;
  goHome: () => void;
  resetGame: () => void;
}

export const useGameStore = create<GameStore>()(
  persist(
    (set, get) => ({
      // Initial state
      gameState: 'selecting',
      cities: cities,
      selectedCity: null,
      cityData: null,
      currentQuestion: null,
      selectedAnswer: null,
      isCorrect: null,
      score: 0,
      totalQuestions: 0,
      progress: {},
      
      // Actions
      selectCity: async (cityId: string) => {
        const city = get().cities.find(c => c.id === cityId);
        if (!city) return;
        
        // Load city subway data
        const cityDataModule = await import(`../data/${cityId}.json`);
        const cityData = cityDataModule.default as CityData;
        
        // Set line colors for the UI
        const colors: Record<string, string> = {};
        cityData.lines.forEach(line => {
          colors[line.id] = line.color;
        });
        setLineColors(colors);
        
        set({
          selectedCity: city,
          cityData: cityData,
          gameState: 'playing'
        });
        
        get().generateQuestion();
      },
      
      generateQuestion: () => {
        const { cityData, selectedCity, progress } = get();
        if (!cityData || !selectedCity) return;
        
        // Get random start/end stations
        const { start, end } = generateRandomStations(cityData);
        
        // Calculate correct route
        const correctRoute = findShortestRoute(start.id, end.id, cityData);
        if (!correctRoute) return;
        
        // Generate options
        const allStations = cityData.lines.flatMap(l => l.stations);
        const options = generateQuestionOptions(correctRoute, allStations, cityData);
        
        // Update progress
        const cityProgress = progress[selectedCity.id] || {
          cityId: selectedCity.id,
          correctCount: 0,
          totalCount: 0,
          lastPlayed: new Date().toISOString()
        };
        
        set({
          currentQuestion: {
            cityId: selectedCity.id,
            startStation: start,
            endStation: end,
            correctRoute,
            options
          },
          selectedAnswer: null,
          isCorrect: null,
          totalQuestions: get().totalQuestions + 1,
          progress: {
            ...progress,
            [selectedCity.id]: {
              ...cityProgress,
              totalCount: cityProgress.totalCount + 1,
              lastPlayed: new Date().toISOString()
            }
          }
        });
      },
      
      selectAnswer: (route: Route) => {
        const { currentQuestion } = get();
        if (!currentQuestion) return;
        
        const isCorrect = route === currentQuestion.correctRoute;
        
        if (isCorrect) {
          set({
            selectedAnswer: route,
            isCorrect: true,
            score: get().score + 1,
            progress: {
              ...get().progress,
              [currentQuestion.cityId]: {
                ...get().progress[currentQuestion.cityId],
                correctCount: get().progress[currentQuestion.cityId].correctCount + 1
              }
            }
          });
        } else {
          set({
            selectedAnswer: route,
            isCorrect: false
          });
        }
      },
      
      nextQuestion: () => {
        set({ gameState: 'feedback' });
        
        setTimeout(() => {
          set({ gameState: 'playing' });
          get().generateQuestion();
        }, 2000);
      },
      
      goHome: () => {
        set({
          gameState: 'selecting',
          selectedCity: null,
          cityData: null,
          currentQuestion: null,
          selectedAnswer: null,
          isCorrect: null
        });
      },
      
      resetGame: () => {
        set({
          score: 0,
          totalQuestions: 0,
          progress: {}
        });
      }
    }),
    {
      name: 'subway-game-storage',
      partialize: (state) => ({
        score: state.score,
        totalQuestions: state.totalQuestions,
        progress: state.progress
      })
    }
  )
);
