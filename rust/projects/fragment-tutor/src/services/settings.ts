import { invoke } from '@tauri-apps/api/core';
import type { UserSettings } from '../types';

export const settingsService = {
  async getSettings(): Promise<UserSettings> {
    return invoke('get_settings') as Promise<UserSettings>;
  },

  async saveApiKey(apiKey: string): Promise<boolean> {
    return invoke('save_api_key', { apiKey }) as Promise<boolean>;
  },

  async getApiKeyStatus(): Promise<boolean> {
    return invoke('get_api_key_status') as Promise<boolean>;
  }
};
