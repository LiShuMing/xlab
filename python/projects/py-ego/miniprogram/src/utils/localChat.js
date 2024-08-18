import { getRoleName } from "./roles";
import { scopedStorageKey } from "./authState";

const STORAGE_KEY = "py_ego_local_chat_messages";

const WELCOME_MESSAGE = {
  id: "welcome",
  role: "assistant",
  content: "我在。你可以从一个小片段开始，不需要完整，也不需要马上解释清楚。",
};

function withTimestamp(message) {
  return {
    created_at: new Date().toISOString(),
    ...message,
  };
}

export function getWelcomeMessage(roleId = "therapist") {
  return withTimestamp({
    ...WELCOME_MESSAGE,
    role_id: roleId,
    role_label: getRoleName(roleId),
  });
}

export function loadLocalChatMessages(roleId = "therapist") {
  const messages = uni.getStorageSync(scopedStorageKey(STORAGE_KEY));
  if (!Array.isArray(messages) || messages.length === 0) {
    return [getWelcomeMessage(roleId)];
  }
  if (messages.length === 1 && messages[0].id === "welcome") {
    return [getWelcomeMessage(roleId)];
  }
  return messages;
}

export function saveLocalChatMessages(messages) {
  uni.setStorageSync(scopedStorageKey(STORAGE_KEY), messages.slice(-80));
}
