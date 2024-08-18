<template>
  <view class="page-shell">
    <NavBar label="LOGIN" status="6 digit" />

    <view class="grid-panel">
      <view class="section">
        <text class="kicker">SIMPLE ACCOUNT</text>
        <text class="hero-title">登录</text>
        <text class="body-text">输入 6 位数字即可。系统会用登录地 / IP 与这 6 位数字组成你的独立账号。</text>
      </view>

      <view class="section">
        <input
          v-model="pin"
          class="input-line pin-input"
          maxlength="6"
          type="text"
          placeholder="000000"
          @input="normalizePin"
        />
        <view class="login-row">
          <button class="ego-button" :disabled="pin.length !== 6 || loggingIn" @tap="submit">
            进入
          </button>
          <text class="mono muted">{{ pin.length }}/6</text>
        </view>
      </view>

      <view class="section">
        <view class="terminal">
          <view class="terminal-title">
            <text>account key</text>
            <text>[private]</text>
          </view>
          <text>$ account = hash(client_ip + pin)\n</text>
          <text>$ chat storage = account scoped\n</text>
          <text>每个账号拥有独立聊天和本地预览记录。</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from "vue";
import NavBar from "../../components/NavBar.vue";
import { loginWithPin } from "../../api/auth";
import { setAuthSession } from "../../utils/authState";

const pin = ref("");
const loggingIn = ref(false);

function normalizePin(event) {
  pin.value = String(event.detail.value || "").replace(/\D/g, "").slice(0, 6);
}

async function submit() {
  if (pin.value.length !== 6 || loggingIn.value) {
    return;
  }

  loggingIn.value = true;
  try {
    await loginWithPin(pin.value);
    uni.showToast({ title: "已登录", icon: "none" });
  } catch (error) {
    setAuthSession({
      accountId: `local-pin-${pin.value}`,
      accountLabel: `PIN-${pin.value}`,
    });
    uni.showToast({ title: "后端未连接，使用本地账号", icon: "none" });
  } finally {
    loggingIn.value = false;
    uni.switchTab({ url: "/pages/chat/index" });
  }
}
</script>

<style scoped>
.pin-input {
  min-height: 112rpx;
  font-size: 48rpx;
  letter-spacing: 12rpx;
}

.login-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 24rpx;
}

.muted {
  color: var(--ego-muted);
  font-size: 20rpx;
}
</style>
