<template>
  <view class="page-shell">
    <NavBar :label="today" status="ready" />

    <view class="grid-panel">
      <view class="section hero-section">
        <text class="kicker">DAILY RECORD</text>
        <text class="hero-title">今日记录</text>
        <text class="body-text">{{ greetingText }}</text>
      </view>

      <view class="section">
        <textarea
          v-model="draft"
          class="input-line record-input"
          maxlength="1000"
          placeholder="写下此刻的想法"
          auto-height
        />
        <view class="save-row">
          <button class="ego-button" @tap="saveText">保存</button>
          <text class="mono save-hint">{{ draft.length }}/1000</text>
        </view>
      </view>

      <view v-if="aiFeedback" class="section">
        <view class="terminal feedback-terminal">
          <view class="terminal-title">
            <text>model feedback</text>
            <text>[{{ getRoleName(currentRoleId) }}]</text>
          </view>
          <text class="feedback-line">$ summarize latest_record\n</text>
          <text class="feedback-answer">{{ aiFeedback.summary }}\n\n</text>
          <text class="feedback-line">$ respond --role therapist\n</text>
          <text class="feedback-answer">{{ aiFeedback.response }}\n\n</text>
          <text class="feedback-line">$ follow_up\n</text>
          <text
            v-for="prompt in aiFeedback.prompts"
            :key="prompt"
            class="feedback-answer"
          >
            - {{ prompt }}\n
          </text>
        </view>
      </view>

      <view class="section">
        <view class="role-row">
          <text class="mono muted">account: {{ accountLabel }} / role: {{ getRoleName(currentRoleId) }}</text>
          <button class="ego-button ghost-button role-button" @tap="openRoles">切换角色</button>
        </view>
        <view class="split-actions">
          <button class="split-action" @tap="focusText">
            <text class="split-action-title">文字</text>
            <text class="split-action-meta">TEXT</text>
          </button>
          <button class="split-action" @tap="openVoice">
            <text class="split-action-title">语音</text>
            <text class="split-action-meta">VOICE</text>
          </button>
          <button class="split-action" @tap="choosePhoto">
            <text class="split-action-title">拍照</text>
            <text class="split-action-meta">PHOTO</text>
          </button>
        </view>
      </view>

      <view class="section">
        <view class="section-heading">
          <text class="section-title">今日记录</text>
          <text class="mono muted">{{ records.length }} items</text>
        </view>
        <RecordCard
          v-for="record in records"
          :key="record.id"
          :record="record"
          @open="openRecord"
        />
        <view v-if="records.length === 0" class="empty mono">No records yet.</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import NavBar from "../../components/NavBar.vue";
import RecordCard from "../../components/RecordCard.vue";
import { createRecord, listRecords } from "../../api/record";
import { greeting, todayLabel } from "../../utils/date";
import { generateRecordFeedback } from "../../utils/aiFeedback";
import { listLocalRecords, saveLocalRecord } from "../../utils/localRecords";
import { getCurrentRoleId, getRoleName } from "../../utils/roles";
import { getAccountLabel, requireLogin } from "../../utils/authState";

const today = todayLabel();
const greetingText = greeting();
const draft = ref("");
const records = ref([]);
const aiFeedback = ref(null);
const currentRoleId = ref(getCurrentRoleId());
const accountLabel = ref(getAccountLabel());

async function loadRecords() {
  if (!requireLogin()) {
    return;
  }
  accountLabel.value = getAccountLabel();
  try {
    const response = await listRecords({ page: 1, size: 20, record_date: today });
    records.value = [...listLocalRecords(), ...(response.items || [])];
  } catch (error) {
    records.value = listLocalRecords();
  }
}

async function saveText() {
  const content = draft.value.trim();
  if (!content) {
    return;
  }

  try {
    const record = await createRecord({
      content_type: "text",
      content,
    });
    records.value = [record, ...records.value];
  } catch (error) {
    const localRecord = saveLocalRecord({
      id: `local-${Date.now()}`,
      content_type: "text",
      content,
      record_date: today,
      created_at: new Date().toISOString(),
    });
    records.value = [localRecord, ...records.value];
    uni.showToast({ title: "后端未连接，已本地预览", icon: "none" });
  }
  currentRoleId.value = getCurrentRoleId();
  aiFeedback.value = generateRecordFeedback(content, currentRoleId.value);
  draft.value = "";
}

function focusText() {
  uni.pageScrollTo({ scrollTop: 0, duration: 180 });
}

function openVoice() {
  uni.navigateTo({ url: "/pages/record/index?mode=voice" });
}

function choosePhoto() {
  uni.chooseImage({
    count: 1,
    sourceType: ["camera", "album"],
    success: (result) => {
      uni.navigateTo({
        url: `/pages/record/index?mode=photo&path=${encodeURIComponent(result.tempFilePaths[0])}`,
      });
    },
  });
}

function openRecord(record) {
  uni.navigateTo({ url: `/pages/record/index?id=${record.id}` });
}

function openRoles() {
  uni.navigateTo({ url: "/pages/role/index" });
}

onMounted(loadRecords);
onShow(() => {
  if (!requireLogin()) {
    return;
  }
  accountLabel.value = getAccountLabel();
  currentRoleId.value = getCurrentRoleId();
  loadRecords();
});
</script>

<style scoped>
.hero-section {
  min-height: 320rpx;
}

.record-input {
  min-height: 220rpx;
  line-height: 1.65;
}

.save-row,
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 22rpx;
}

.save-hint,
.muted,
.empty {
  color: var(--ego-muted);
  font-size: 20rpx;
}

.empty {
  padding-top: 28rpx;
}

.role-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 22rpx;
}

.role-button {
  min-height: 64rpx;
  padding: 0 22rpx;
  font-size: 24rpx;
}

.feedback-terminal {
  white-space: pre-wrap;
}

.feedback-line {
  color: var(--ego-muted);
}

.feedback-answer {
  color: var(--ego-ink);
}
</style>
