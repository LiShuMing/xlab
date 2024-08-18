<template>
  <view class="page-shell">
    <NavBar label="TIMELINE" :status="month" />

    <view class="grid-panel">
      <view class="section">
        <text class="kicker">MONTH</text>
        <text class="hero-title">时间线</text>
        <view class="month-row">
          <input v-model="month" class="input-line month-input" />
          <button class="ego-button" @tap="loadTimeline">查询</button>
        </view>
      </view>

      <view class="section">
        <view v-for="day in days" :key="day.date" class="day-row" @tap="openDay(day)">
          <view>
            <text class="day-date mono">{{ day.date }}</text>
            <text class="day-preview">{{ day.preview || "No preview" }}</text>
          </view>
          <text class="day-count mono">{{ day.count }}</text>
        </view>
        <view v-if="days.length === 0" class="empty mono">No timeline data.</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onMounted, ref } from "vue";
import NavBar from "../../components/NavBar.vue";
import { getTimeline } from "../../api/record";
import { currentMonth } from "../../utils/date";

const month = ref(currentMonth());
const days = ref([]);

async function loadTimeline() {
  try {
    const response = await getTimeline(month.value);
    days.value = response.days || [];
  } catch (error) {
    days.value = [];
  }
}

function openDay(day) {
  uni.setStorageSync("py_ego_selected_date", day.date);
  uni.switchTab({ url: "/pages/index/index" });
}

onMounted(loadTimeline);
</script>

<style scoped>
.month-row {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.month-input {
  flex: 1;
}

.day-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 26rpx 0;
  border-top: 1px solid var(--ego-line);
}

.day-row:first-child {
  border-top: 0;
}

.day-date,
.day-preview {
  display: block;
}

.day-date,
.day-count,
.empty {
  color: var(--ego-muted);
  font-size: 20rpx;
}

.day-preview {
  margin-top: 10rpx;
  color: var(--ego-ink);
  font-size: 28rpx;
  line-height: 1.55;
}

.day-count {
  min-width: 50rpx;
  text-align: right;
}
</style>
