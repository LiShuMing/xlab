<template>
  <view class="topline">
    <text class="nav-label">{{ label }}</text>
    <text class="nav-status">{{ status }}</text>
  </view>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  status: {
    type: String,
    default: "memory online",
  },
});
</script>
