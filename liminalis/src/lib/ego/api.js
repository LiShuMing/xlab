import { fetchJson } from '../api';
import { getToken } from './authState';

async function egoFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetchJson(`/api/ego${path}`, { ...options, headers });
}

// Auth
export function loginWithPin(pin) {
  return egoFetch('/auth/pin-login', { method: 'POST', body: JSON.stringify({ pin }) });
}

// Chat
export function createSession(roleId = 'therapist') {
  return egoFetch('/chat/sessions', { method: 'POST', body: JSON.stringify({ role_id: roleId }) });
}

export function listSessions() {
  return egoFetch('/chat/sessions');
}

export function sendMessage(sessionId, content) {
  return egoFetch(`/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function listMessages(sessionId) {
  return egoFetch(`/chat/sessions/${sessionId}/messages`);
}

// Records
export function createRecord(payload) {
  return egoFetch('/records', { method: 'POST', body: JSON.stringify(payload) });
}

export function listRecords(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return egoFetch(`/records${qs ? '?' + qs : ''}`);
}

export function getTimeline(month) {
  return egoFetch(`/records/timeline?month=${encodeURIComponent(month)}`);
}

export function getRecord(recordId) {
  return egoFetch(`/records/${recordId}`);
}

export function deleteRecord(recordId) {
  return egoFetch(`/records/${recordId}`, { method: 'DELETE' });
}

// Roles
export function listRoles() {
  return egoFetch('/roles');
}

export function getCurrentRole() {
  return egoFetch('/roles/current');
}

export function updateCurrentRole(roleId) {
  return egoFetch('/roles/current', {
    method: 'PUT',
    body: JSON.stringify({ role_id: roleId }),
  });
}
