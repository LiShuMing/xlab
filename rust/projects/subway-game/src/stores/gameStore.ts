import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { City, CityData, Question, GameState, GameProgress, Route, DifficultyMode } from '../types';
import { generateRandomStationsByDifficulty, generateQuestionOptions } from '../utils/routeCalculator';
import citiesData from '../data/cities.json';

// Type assertion for cities data
const cities: City[] = citiesData.cities.map(city => ({
  ...city,
  difficulty: city.difficulty as 'easy' | 'medium' | 'hard'
}));

const cityDataLoaders = import.meta.glob<{ default: CityData }>(['../data/*.json', '!../data/cities.json']);

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
  sessionQuestion: number;
  sessionLength: number;
  sessionCorrect: number;
  difficulty: DifficultyMode;
  isLoadingCity: boolean;
  loadError: string | null;
  progress: Record<string, GameProgress>;
  
  // Actions
  selectDifficulty: (difficulty: DifficultyMode) => void;
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
      sessionQuestion: 0,
      sessionLength: 5,
      sessionCorrect: 0,
      difficulty: 'easy',
      isLoadingCity: false,
      loadError: null,
      progress: {},

      selectDifficulty: (difficulty: DifficultyMode) => {
        set({ difficulty });
      },
      
      // Actions
      selectCity: async (cityId: string) => {
        if (get().isLoadingCity) return;
        const city = get().cities.find(c => c.id === cityId);
        if (!city) return;

        set({
          isLoadingCity: true,
          loadError: null,
          gameState: 'selecting',
          selectedCity: null,
          cityData: null,
          currentQuestion: null,
          selectedAnswer: null,
          isCorrect: null,
          sessionQuestion: 0,
          sessionCorrect: 0
        });
        
        // Load city subway data
        const loadCityData = cityDataLoaders[`../data/${cityId}.json`];
        if (!loadCityData) {
          set({
            isLoadingCity: false,
            loadError: `没有找到 ${city.name} 的地铁数据`
          });
          return;
        }

        try {
          const cityDataModule = await loadCityData();
          const cityData = cityDataModule.default;

          set({
            selectedCity: city,
            cityData: cityData,
            gameState: 'playing',
            sessionQuestion: 0,
            sessionCorrect: 0,
            currentQuestion: null,
            selectedAnswer: null,
            isCorrect: null
          });

          get().generateQuestion();
          set({ isLoadingCity: false, loadError: null });
        } catch (error) {
          console.error('Failed to start city game', error);
          set({
            isLoadingCity: false,
            gameState: 'selecting',
            selectedCity: null,
            cityData: null,
            currentQuestion: null,
            selectedAnswer: null,
            isCorrect: null,
            loadError: `${city.name} 暂时没有准备好，再点一次试试`
          });
        }
      },
      
      generateQuestion: () => {
        const { cityData, selectedCity, progress, difficulty } = get();
        if (!cityData || !selectedCity) return;
        
        const { start, end, route: correctRoute } = generateRandomStationsByDifficulty(cityData, difficulty);
        
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
          gameState: 'playing',
          sessionQuestion: get().sessionQuestion + 1,
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
        const cityProgress = get().progress[currentQuestion.cityId] || {
          cityId: currentQuestion.cityId,
          correctCount: 0,
          totalCount: 0,
          lastPlayed: new Date().toISOString()
        };
        
        if (isCorrect) {
          set({
            selectedAnswer: route,
            isCorrect: true,
            gameState: 'feedback',
            score: get().score + 1,
            sessionCorrect: get().sessionCorrect + 1,
            progress: {
              ...get().progress,
              [currentQuestion.cityId]: {
                ...cityProgress,
                correctCount: cityProgress.correctCount + 1,
                lastPlayed: new Date().toISOString()
              }
            }
          });
        } else {
          set({
            selectedAnswer: route,
            isCorrect: false,
            gameState: 'feedback'
          });
        }
      },
      
      nextQuestion: () => {
        const { sessionQuestion, sessionLength } = get();
        if (sessionQuestion >= sessionLength) {
          set({ gameState: 'complete' });
          return;
        }
        get().generateQuestion();
      },
      
      goHome: () => {
        set({
          gameState: 'selecting',
          selectedCity: null,
          cityData: null,
          currentQuestion: null,
          selectedAnswer: null,
          isCorrect: null,
          sessionQuestion: 0,
          sessionCorrect: 0
        });
      },
      
      resetGame: () => {
        set({
          score: 0,
          totalQuestions: 0,
          sessionQuestion: 0,
          sessionCorrect: 0,
          progress: {}
        });
      }
    }),
    {
      name: 'subway-game-storage',
      partialize: (state) => ({
        score: state.score,
        totalQuestions: state.totalQuestions,
        difficulty: state.difficulty,
        progress: state.progress
      })
    }
  )
);
