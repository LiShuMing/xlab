import { request } from "./request";
import { setAuthSession } from "../utils/authState";

export async function loginWithWechat(code) {
  const response = await request({
    url: "/auth/login",
    method: "POST",
    data: { code },
    auth: false,
  });

  if (response.token) {
    setAuthSession({
      token: response.token,
      refreshToken: response.refresh_token,
      accountId: response.user?.id || "wechat",
      accountLabel: response.user?.nickname || "wechat",
    });
  }

  return response;
}

export async function loginWithPin(pin) {
  const response = await request({
    url: "/auth/pin-login",
    method: "POST",
    data: { pin },
    auth: false,
  });

  if (response.token) {
    setAuthSession({
      token: response.token,
      refreshToken: response.refresh_token,
      accountId: response.user?.id || `pin-${pin}`,
      accountLabel: response.user?.nickname || `PIN-${pin}`,
    });
  }

  return response;
}

export function refreshToken(refreshTokenValue) {
  return request({
    url: "/auth/refresh",
    method: "POST",
    data: { refresh_token: refreshTokenValue },
    auth: false,
  });
}
