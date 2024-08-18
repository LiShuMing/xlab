<template>
  <view class="record-card" @tap="$emit('open', record)">
    <view class="record-head">
      <text class="record-type mono">{{ typeLabel }}</text>
      <text class="record-time mono">{{ timeLabel }}</text>
    </view>
    <text class="record-content">{{ record.content || record.media_url || "No content" }}</text>
  </view>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  record: {
    type: Object,
    required: true,
  },
});

defineEmits(["open"]);

const typeMap = {
  text: "TEXT",
  voice: "VOICE",
  photo: "PHOTO",
};

const typeLabel = computed(() => typeMap[props.record.content_type] || "NOTE");
const timeLabel = computed(() => {
  if (!props.record.created_at) {
    return "--:--";
  }
  const date = new Date(props.record.created_at);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
});
</script>

<style scoped>
.record-card {
  padding: 24rpx 0;
  border-top: 1px solid var(--ego-line);
}

.record-card:first-child {
  border-top: 0;
}

.record-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12rpx;
  color: var(--ego-muted);
  font-size: 20rpx;
}

.record-content {
  display: block;
  color: var(--ego-ink);
  font-size: 28rpx;
  line-height: 1.62;
}
</style>
