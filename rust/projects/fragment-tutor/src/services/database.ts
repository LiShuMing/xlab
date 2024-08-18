import { invoke } from '@tauri-apps/api/core';
import type { Document, ReviewItem, Reflection, ReflectionStats } from '../types';

export const databaseService = {
  // Documents
  async getDocuments(limit?: number, offset?: number): Promise<Document[]> {
    return invoke('get_documents', { limit, offset }) as Promise<Document[]>;
  },

  async getDocument(id: string): Promise<Document | null> {
    try {
      return await invoke('get_document', { id }) as Document;
    } catch {
      return null;
    }
  },

  async deleteDocument(id: string): Promise<boolean> {
    return invoke('delete_document', { id }) as Promise<boolean>;
  },

  async searchDocuments(query: string): Promise<Document[]> {
    return invoke('search_documents', { query }) as Promise<Document[]>;
  },

  async updateDocumentStatus(id: string, status: string): Promise<boolean> {
    return invoke('update_document_status', { id, status }) as Promise<boolean>;
  },

  // Reviews
  async getReviewQueue(): Promise<ReviewItem[]> {
    return invoke('get_review_queue') as Promise<ReviewItem[]>;
  },

  async getReviewsForDate(date: string): Promise<ReviewItem[]> {
    return invoke('get_reviews_for_date', { date }) as Promise<ReviewItem[]>;
  },

  async submitReview(itemId: string, score: number): Promise<void> {
    await invoke('submit_review', { itemId, score });
  },

  async createVocabCard(
    word: string,
    definition: string,
    context: string,
    documentId?: string
  ): Promise<ReviewItem> {
    return invoke('create_vocab_card', { word, definition, context, documentId }) as Promise<ReviewItem>;
  },

  async createInsightCard(
    insight: string,
    context: string,
    documentId?: string
  ): Promise<ReviewItem> {
    return invoke('create_insight_card', { insight, context, documentId }) as Promise<ReviewItem>;
  },

  // Reflections
  async getReflection(date: string): Promise<Reflection | null> {
    try {
      return await invoke('get_reflection', { date }) as Reflection;
    } catch {
      return null;
    }
  },

  async saveReflection(reflection: {
    keyWin: string;
    avoidance: string;
    nextFix: string;
    deepWorkMin: number;
    familyMin: number;
    sleepH: number;
    notes?: string;
  }): Promise<Reflection> {
    return invoke('save_reflection', { ...reflection, date: undefined }) as Promise<Reflection>;
  },

  async getReflectionLog(startDate?: string, endDate?: string): Promise<Reflection[]> {
    return invoke('get_reflection_log', { startDate, endDate }) as Promise<Reflection[]>;
  },

  async getReflectionStats(): Promise<ReflectionStats> {
    return invoke('get_reflection_stats') as Promise<ReflectionStats>;
  }
};
