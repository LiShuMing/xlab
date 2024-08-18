<template>
  <view class="voice-box">
    <button class="ego-button ghost-button voice-button" @tap="$emit('start')">
      HOLD TO SPEAK
    </button>
    <text class="voice-note mono">WeChat speech plugin returns editable text before saving.</text>
  </view>
</template>

<script setup>
defineEmits(["start"]);
</script>

<style scoped>
.voice-box {
  display: grid;
  gap: 16rpx;
}

.voice-button {
  width: 100%;
}

.voice-note {
  color: var(--ego-muted);
  font-size: 20rpx;
  line-height: 1.5;
}
</style>
