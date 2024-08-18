import { clearAuthSession, getToken, setAuthSession } from "../utils/authState";

const BASE_URL = "http://localhost:8000/api";

export function setToken(token) {
  setAuthSession({ token, accountId: "legacy", accountLabel: "legacy" });
}

export function clearToken() {
  clearAuthSession();
}

export function request({ url, method = "GET", data = undefined, auth = true }) {
  const token = getToken();
  const header = {
    "Content-Type": "application/json",
  };

  if (auth && token) {
    header.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${url}`,
      method,
      data,
      header,
      timeout: 3500,
      success: (response) => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        reject(response.data || { message: "Request failed" });
      },
      fail: reject,
    });
  });
}
