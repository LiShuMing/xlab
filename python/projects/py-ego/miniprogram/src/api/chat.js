import { request } from "./request";
import { buildQuery } from "../utils/query";

export function createSession(roleId = "therapist") {
  return request({
    url: "/chat/sessions",
    method: "POST",
    data: { role_id: roleId },
  });
}

export function listSessions(params = {}) {
  return request({
    url: `/chat/sessions${buildQuery(params)}`,
  });
}

export function sendMessage(sessionId, content) {
  return request({
    url: `/chat/sessions/${sessionId}/messages`,
    method: "POST",
    data: { content },
  });
}

export function listMessages(sessionId, params = {}) {
  return request({
    url: `/chat/sessions/${sessionId}/messages${buildQuery(params)}`,
  });
}
