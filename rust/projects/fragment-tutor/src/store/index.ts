import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Document, ReviewItem, QuickDigestResult, UserSettings } from '../types';

interface AppState {
  // Navigation
  currentView: 'library' | 'today' | 'review' | 'reflection' | 'settings';
  setCurrentView: (view: AppState['currentView']) => void;

  // Documents
  documents: Document[];
  setDocuments: (docs: Document[]) => void;
  addDocument: (doc: Document) => void;
  removeDocument: (id: string) => void;
  selectedDocument: Document | null;
  setSelectedDocument: (doc: Document | null) => void;

  // Analysis
  currentAnalysis: QuickDigestResult | null;
  setCurrentAnalysis: (analysis: QuickDigestResult | null) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (analyzing: boolean) => void;

  // Reviews
  reviewQueue: ReviewItem[];
  setReviewQueue: (queue: ReviewItem[]) => void;
  currentReviewItem: ReviewItem | null;
  setCurrentReviewItem: (item: ReviewItem | null) => void;

  // Settings
  settings: UserSettings;
  setSettings: (settings: UserSettings) => void;
  apiKey: string | null;
  setApiKey: (key: string | null) => void;

  // UI State
  isCaptureModalOpen: boolean;
  setIsCaptureModalOpen: (open: boolean) => void;
  isReflectionCardOpen: boolean;
  setIsReflectionCardOpen: (open: boolean) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Navigation
      currentView: 'library',
      setCurrentView: (view) => set({ currentView: view }),

      // Documents
      documents: [],
      setDocuments: (docs) => set({ documents: docs }),
      addDocument: (doc) => set((state) => ({ 
        documents: [doc, ...state.documents] 
      })),
      removeDocument: (id) => set((state) => ({ 
        documents: state.documents.filter((d) => d.id !== id) 
      })),
      selectedDocument: null,
      setSelectedDocument: (doc) => set({ selectedDocument: doc }),

      // Analysis
      currentAnalysis: null,
      setCurrentAnalysis: (analysis) => set({ currentAnalysis: analysis }),
      isAnalyzing: false,
      setIsAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),

      // Reviews
      reviewQueue: [],
      setReviewQueue: (queue) => set({ reviewQueue: queue }),
      currentReviewItem: null,
      setCurrentReviewItem: (item) => set({ currentReviewItem: item }),

      // Settings
      settings: {
        notification: {
          reviewReminder: true,
          reviewTime: '09:00',
          eveningReminder: true,
          eveningTime: '22:00',
          reflectionReminder: false,
          reflectionInterval: 3,
        },
        dailyGoalReviews: 20,
        dailyGoalDeepWorkMin: 120,
        shortcutKey: 'CmdOrCtrl+Shift+R',
      },
      setSettings: (settings) => set({ settings }),
      apiKey: null,
      setApiKey: (key) => set({ apiKey: key }),

      // UI State
      isCaptureModalOpen: false,
      setIsCaptureModalOpen: (open) => set({ isCaptureModalOpen: open }),
      isReflectionCardOpen: false,
      setIsReflectionCardOpen: (open) => set({ isReflectionCardOpen: open }),
    }),
    {
      name: 'fragment-tutor-storage',
      partialize: (state) => ({
        apiKey: state.apiKey,
        settings: state.settings,
      }),
    }
  )
);
