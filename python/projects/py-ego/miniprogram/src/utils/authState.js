const TOKEN_KEY = "py_ego_token";
const REFRESH_TOKEN_KEY = "py_ego_refresh_token";
const ACCOUNT_KEY = "py_ego_account_id";
const ACCOUNT_LABEL_KEY = "py_ego_account_label";

export function setAuthSession({ token, refreshToken, accountId, accountLabel }) {
  if (token) {
    uni.setStorageSync(TOKEN_KEY, token);
  }
  if (refreshToken) {
    uni.setStorageSync(REFRESH_TOKEN_KEY, refreshToken);
  }
  uni.setStorageSync(ACCOUNT_KEY, accountId);
  uni.setStorageSync(ACCOUNT_LABEL_KEY, accountLabel || accountId);
}

export function clearAuthSession() {
  uni.removeStorageSync(TOKEN_KEY);
  uni.removeStorageSync(REFRESH_TOKEN_KEY);
  uni.removeStorageSync(ACCOUNT_KEY);
  uni.removeStorageSync(ACCOUNT_LABEL_KEY);
}

export function getToken() {
  return uni.getStorageSync(TOKEN_KEY) || "";
}

export function getAccountId() {
  return uni.getStorageSync(ACCOUNT_KEY) || "";
}

export function getAccountLabel() {
  return uni.getStorageSync(ACCOUNT_LABEL_KEY) || "";
}

export function isLoggedIn() {
  return Boolean(getAccountId());
}

export function requireLogin() {
  if (isLoggedIn()) {
    return true;
  }
  uni.navigateTo({ url: "/pages/login/index" });
  return false;
}

export function scopedStorageKey(baseKey) {
  return `${baseKey}:${getAccountId() || "guest"}`;
}
