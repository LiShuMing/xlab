import { getItem, setItem, removeItem } from './storage';

const TOKEN_KEY = 'token';
const ACCOUNT_KEY = 'account_id';
const ACCOUNT_LABEL_KEY = 'account_label';

export function setAuthSession({ token, accountId, accountLabel }) {
  if (token) setItem(TOKEN_KEY, token);
  setItem(ACCOUNT_KEY, accountId);
  setItem(ACCOUNT_LABEL_KEY, accountLabel || accountId);
}

export function clearAuthSession() {
  removeItem(TOKEN_KEY);
  removeItem(ACCOUNT_KEY);
  removeItem(ACCOUNT_LABEL_KEY);
}

export function getToken() {
  return getItem(TOKEN_KEY) || '';
}

export function getAccountId() {
  return getItem(ACCOUNT_KEY) || '';
}

export function getAccountLabel() {
  return getItem(ACCOUNT_LABEL_KEY) || '';
}

export function isLoggedIn() {
  return Boolean(getAccountId());
}

export function scopedStorageKey(baseKey) {
  return `${baseKey}:${getAccountId() || 'guest'}`;
}
