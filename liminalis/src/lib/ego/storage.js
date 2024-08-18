const PREFIX = 'ego_';

export function getItem(key) {
  try {
    return JSON.parse(localStorage.getItem(PREFIX + key));
  } catch {
    return null;
  }
}

export function setItem(key, value) {
  localStorage.setItem(PREFIX + key, JSON.stringify(value));
}

export function removeItem(key) {
  localStorage.removeItem(PREFIX + key);
}
