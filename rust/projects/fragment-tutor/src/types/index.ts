// Document Types
export interface Document {
  id: string;
  type: 'url' | 'note';
  title: string;
  url?: string;
  content?: string;
  capturedAt: string;
  cleanTextPath?: string;
  rawHtmlPath?: string;
  status: DocumentStatus;
  topics: string[];
  entities: string[];
  wordCount: number;
}

export type DocumentStatus = 'captured' | 'ingested' | 'analyzing' | 'analyzed' | 'failed';

export interface DocumentListItem {
  id: string;
  title: string;
  type: 'url' | 'note';
  url?: string;
  capturedAt: string;
  status: DocumentStatus;
  hasAnalysis: boolean;
  wordCount?: number;
}

// Analysis Types
export interface Analysis {
  id: string;
  documentId: string;
  mode: 'quick' | 'deep';
  createdAt: string;
  costMs: number;
  result: QuickDigestResult;
}

export interface QuickDigestResult {
  thesis: string;
  firstPrinciples: string[];
  counterpoint: string;
  microActions: string[];
  vocab: VocabularyItem[];
  keyInsights: string[];
  relatedTopics: string[];
}

export interface VocabularyItem {
  word: string;
  definition: string;
  context: string;
  pronunciation?: string;
}

// Review Types
export interface ReviewItem {
  id: string;
  type: 'vocab' | 'insight';
  itemId: string;
  itemType: string;
  front: string;
  back: string;
  context?: string;
  dueAt: string;
  interval: number;
  ease: number;
  lastScore: number | null;
  streak: number;
  createdAt: string;
}

export interface ReviewQueue {
  due: ReviewItem[];
  learning: ReviewItem[];
}

export interface SRSResult {
  itemId: string;
  newInterval: number;
  newEase: number;
  nextDueAt: string;
}

// Reflection Types
export interface Reflection {
  id: string;
  date: string;
  keyWin?: string;
  avoidance?: string;
  nextFix?: string;
  deepWorkMin: number;
  familyMin: number;
  sleepH: number;
  notes?: string;
  createdAt: string;
}

export interface ReflectionStats {
  totalReflections: number;
  avgDeepWorkMin: number;
  avgFamilyMin: number;
  avgSleepH: number;
  currentStreak: number;
  recentWins: string[];
  commonAvoidance: string[];
}

export interface ReflectionInput {
  date?: string;
  keyWin: string;
  avoidance: string;
  nextFix: string;
  deepWorkMin: number;
  familyMin: number;
  sleepH: number;
  notes?: string;
}

// Notification Types
export interface NotificationConfig {
  reviewReminder: boolean;
  reviewTime: string; // HH:mm format
  eveningReminder: boolean;
  eveningTime: string;
  reflectionReminder: boolean;
  reflectionInterval: number; // hours
}

// Settings Types
export interface UserSettings {
  anthropicApiKey?: string;
  notification: NotificationConfig;
  dailyGoalReviews: number;
  dailyGoalDeepWorkMin: number;
  shortcutKey: string;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Capture Request
export interface CaptureRequest {
  url: string;
  title?: string;
}

export interface NoteRequest {
  title: string;
  content: string;
}

// Search
export interface SearchResult {
  documents: Document[];
  total: number;
}
