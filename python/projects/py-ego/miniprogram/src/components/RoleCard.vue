<template>
  <view :class="['role-card', selected ? 'role-card-selected' : '']">
    <view class="role-content" @tap="$emit('select', role)">
      <text class="role-name">{{ role.name }}</text>
      <text class="role-id mono">{{ role.id }}</text>
      <text v-if="role.description" class="role-description">{{ role.description }}</text>
    </view>
    <view class="role-actions">
      <text class="role-marker mono">{{ selected ? "[x]" : "[ ]" }}</text>
      <button
        :class="['ego-button', 'role-select-button', selected ? '' : 'ghost-button']"
        @tap.stop="$emit('select', role)"
      >
        {{ selected ? "当前使用" : "使用此角色" }}
      </button>
    </view>
  </view>
</template>

<script setup>
defineProps({
  role: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["select"]);
</script>

<style scoped>
.role-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 26rpx 0;
  border-top: 1px solid var(--ego-line);
}

.role-content {
  flex: 1;
  min-width: 0;
}

.role-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 18rpx;
}

.role-card:first-child {
  border-top: 0;
}

.role-name,
.role-id,
.role-description {
  display: block;
}

.role-name {
  margin-bottom: 8rpx;
  color: var(--ego-ink);
  font-size: 30rpx;
  font-weight: 700;
}

.role-id,
.role-marker {
  color: var(--ego-muted);
  font-size: 20rpx;
}

.role-description {
  margin-top: 14rpx;
  color: var(--ego-muted);
  font-size: 24rpx;
  line-height: 1.55;
}

.role-card-selected .role-marker {
  color: var(--ego-ink);
}

.role-select-button {
  min-height: 64rpx;
  padding: 0 22rpx;
  font-size: 24rpx;
}
</style>
