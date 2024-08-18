<template>
  <view :class="['bubble', message.role === 'user' ? 'bubble-user' : 'bubble-agent']">
    <view class="bubble-head mono">
      <text>{{ speakerLabel }}</text>
      <text>{{ timeLabel }}</text>
    </view>
    <text class="bubble-body">{{ message.content }}</text>
  </view>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
  roleName: {
    type: String,
    default: "EGO",
  },
});

const speakerLabel = computed(() => {
  if (props.message.role === "user") {
    return "YOU";
  }
  return props.message.role_label || props.message.role_id?.toUpperCase() || props.roleName;
});

const timeLabel = computed(() => {
  if (!props.message.created_at) {
    return "now";
  }
  const date = new Date(props.message.created_at);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
});
</script>

<style scoped>
.bubble {
  padding: 24rpx;
  border: 1px solid var(--ego-line);
  background: var(--ego-panel);
}

.bubble + .bubble {
  margin-top: 20rpx;
}

.bubble-user {
  margin-left: 52rpx;
}

.bubble-agent {
  margin-right: 52rpx;
  background: #ebe8df;
}

.bubble-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 14rpx;
  color: var(--ego-muted);
  font-size: 20rpx;
}

.bubble-body {
  color: var(--ego-ink);
  font-size: 28rpx;
  line-height: 1.65;
}
</style>
