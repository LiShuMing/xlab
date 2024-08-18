<template>
  <view class="page-shell chat-page">
    <NavBar label="AI COMPANION" :status="roleId" />

    <view class="grid-panel chat-panel">
      <view class="section chat-head">
        <view>
          <text class="kicker">SESSION</text>
          <text class="hero-title">对话</text>
        </view>
        <button class="ego-button ghost-button compact" @tap="openRoles">角色</button>
      </view>

      <view class="section message-list">
        <ChatBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :role-name="roleId.toUpperCase()"
        />
      </view>

      <view class="section composer">
        <textarea
          v-model="draft"
          class="input-line composer-input"
          maxlength="800"
          placeholder="告诉我今天发生了什么"
          auto-height
        />
        <button class="ego-button send-button" :disabled="sending" @tap="submit">
          发送
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import NavBar from "../../components/NavBar.vue";
import ChatBubble from "../../components/ChatBubble.vue";
import { createSession, sendMessage } from "../../api/chat";
import { generateChatReply } from "../../utils/aiFeedback";
import { getCurrentRoleId, getRoleName, setCurrentRoleId } from "../../utils/roles";
import { requireLogin } from "../../utils/authState";
import {
  getWelcomeMessage,
  loadLocalChatMessages,
  saveLocalChatMessages,
} from "../../utils/localChat";

const roleId = ref(getCurrentRoleId());
const sessionId = ref("");
const draft = ref("");
const sending = ref(false);
const messages = ref(loadLocalChatMessages(roleId.value));

function applyRoleFromRoute(options = {}) {
  const routeRoleId = options.role_id || options.roleId || options.role;
  if (!routeRoleId || routeRoleId === roleId.value) {
    return;
  }

  setCurrentRoleId(routeRoleId);
  roleId.value = routeRoleId;
  sessionId.value = "";
  messages.value = loadLocalChatMessages(routeRoleId);
  if (messages.value.length === 0) {
    setMessages([getWelcomeMessage(routeRoleId)]);
  }
}

function setMessages(nextMessages) {
  messages.value = nextMessages;
  saveLocalChatMessages(nextMessages);
}

async function ensureSession() {
  if (sessionId.value) {
    return;
  }
  try {
    const session = await createSession(roleId.value);
    sessionId.value = session.id;
    roleId.value = session.role_id || roleId.value;
  } catch (error) {
    sessionId.value = "";
  }
}

async function submit() {
  const content = draft.value.trim();
  if (!content || sending.value) {
    return;
  }

  sending.value = true;
  const userMessage = {
    id: `local-${Date.now()}`,
    role: "user",
    content,
    created_at: new Date().toISOString(),
  };
  setMessages([...messages.value, userMessage]);
  draft.value = "";

  try {
    await ensureSession();
    if (!sessionId.value) {
      throw new Error("Session unavailable");
    }
    const reply = await sendMessage(sessionId.value, content);
    setMessages([
      ...messages.value,
      {
        id: `reply-${Date.now()}`,
        role: "assistant",
        role_id: roleId.value,
        role_label: getRoleName(roleId.value),
        content: reply.reply,
        created_at: new Date().toISOString(),
      },
    ]);
  } catch (error) {
    setMessages([
      ...messages.value,
      {
        id: `fallback-${Date.now()}`,
        role: "assistant",
        role_id: roleId.value,
        role_label: getRoleName(roleId.value),
        content: generateChatReply(content, roleId.value),
        created_at: new Date().toISOString(),
      },
    ]);
    uni.showToast({ title: "后端未连接，使用本地回应预览", icon: "none" });
  } finally {
    sending.value = false;
  }
}

function handleComposerKeydown(event) {
  const targetTag = event.target?.tagName?.toLowerCase();
  const isComposerFocused = targetTag === "textarea";
  const isEnter = event.key === "Enter" || event.keyCode === 13;
  if (!isComposerFocused || !isEnter || (!event.ctrlKey && !event.metaKey)) {
    return;
  }

  event.preventDefault();
  submit();
}

function openRoles() {
  uni.navigateTo({ url: "/pages/role/index" });
}

function refreshRole() {
  if (!requireLogin()) {
    return;
  }
  const nextRoleId = getCurrentRoleId();
  if (nextRoleId !== roleId.value) {
    roleId.value = nextRoleId;
    sessionId.value = "";
    setMessages([
      ...messages.value,
      {
        id: `role-${Date.now()}`,
        role: "assistant",
        role_id: nextRoleId,
        role_label: getRoleName(nextRoleId),
        content: `已切换到「${getRoleName(nextRoleId)}」。接下来我会用这个视角回应你。`,
        created_at: new Date().toISOString(),
      },
    ]);
  }
}

if (messages.value.length === 0) {
  setMessages([getWelcomeMessage(roleId.value)]);
}

onMounted(() => {
  if (!requireLogin()) {
    return;
  }
  if (typeof document !== "undefined") {
    document.addEventListener("keydown", handleComposerKeydown);
  }
  refreshRole();
  ensureSession();
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined") {
    document.removeEventListener("keydown", handleComposerKeydown);
  }
});

onLoad((options) => {
  applyRoleFromRoute(options);
});

onShow(() => {
  if (!requireLogin()) {
    return;
  }
  messages.value = loadLocalChatMessages(getCurrentRoleId());
  refreshRole();
  ensureSession();
});
</script>

<style scoped>
.chat-panel {
  display: flex;
  min-height: calc(100vh - 150rpx);
  flex-direction: column;
}

.chat-head,
.composer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
}

.chat-head .hero-title {
  margin-bottom: 0;
}

.compact {
  min-height: 72rpx;
  padding: 0 24rpx;
}

.message-list {
  flex: 1;
}

.composer-input {
  min-height: 90rpx;
  flex: 1;
  line-height: 1.55;
}

.send-button {
  min-width: 132rpx;
}
</style>
