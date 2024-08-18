import { invoke } from '@tauri-apps/api/core';
import type { Document } from '../types';

export const captureService = {
  async captureUrl(url: string, title?: string): Promise<Document> {
    return invoke('capture_url', { url, title }) as Promise<Document>;
  },

  async createNote(title: string, content: string): Promise<Document> {
    return invoke('create_note', { title, content }) as Promise<Document>;
  }
};
