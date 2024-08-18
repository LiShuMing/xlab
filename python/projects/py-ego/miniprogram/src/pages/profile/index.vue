<template>
  <view class="page-shell">
    <NavBar label="PROFILE" status="private memory" />

    <view class="grid-panel">
      <view class="section">
        <text class="kicker">PY-EGO</text>
        <text class="hero-title">我</text>
        <text class="body-text">个人记录、角色偏好和长期记忆会一起塑造 AI 的回答方式。</text>
      </view>

      <view class="section">
        <view class="terminal">
          <view class="terminal-title">
            <text>memory</text>
            <text>[local]</text>
          </view>
          <text>$ records sync --today\n</text>
          <text>$ profile update --role therapist\n</text>
          <text>status: waiting for backend profile API</text>
        </view>
      </view>

      <view class="section profile-actions">
        <button class="ego-button ghost-button" @tap="openRoles">角色设置</button>
        <button class="ego-button ghost-button" @tap="exportData">导出数据</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import NavBar from "../../components/NavBar.vue";

function openRoles() {
  uni.navigateTo({ url: "/pages/role/index" });
}

function exportData() {
  uni.showToast({
    title: "待接入 profile/export",
    icon: "none",
  });
}
</script>

<style scoped>
.profile-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
}
</style>
