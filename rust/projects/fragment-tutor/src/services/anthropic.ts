import { invoke } from '@tauri-apps/api/core';
import type { QuickDigestResult } from '../types';

export const anthropicService = {
  async quickDigest(documentId: string, apiKey?: string | null): Promise<QuickDigestResult> {
    const payload = apiKey ? { documentId, apiKey } : { documentId };
    return invoke('quick_digest', payload) as Promise<QuickDigestResult>;
  },

  async getAnalysis(documentId: string): Promise<QuickDigestResult | null> {
    try {
      return await invoke('get_analysis', { documentId }) as QuickDigestResult;
    } catch {
      return null;
    }
  },

  async analyzeDocument(documentId: string, mode: string, apiKey: string): Promise<string> {
    return invoke('analyze_document', { documentId, mode, apiKey }) as Promise<string>;
  }
};
