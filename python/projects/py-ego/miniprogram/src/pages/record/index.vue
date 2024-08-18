<template>
  <view class="page-shell">
    <NavBar label="RECORD DETAIL" :status="mode" />

    <view class="grid-panel">
      <view class="section">
        <text class="kicker">{{ mode.toUpperCase() }}</text>
        <text class="hero-title">记录</text>
        <text class="body-text">保存前可以编辑内容，让它成为更清楚的长期记忆来源。</text>
      </view>

      <view v-if="loadState === 'missing'" class="section">
        <view class="terminal">
          <view class="terminal-title">
            <text>record lookup</text>
            <text>[missing]</text>
          </view>
          <text>$ get {{ recordId }}\n</text>
          <text>这条本地预览记录没有持久化副本。请返回首页重新保存一条记录。</text>
        </view>
      </view>

      <view class="section">
        <VoiceInput v-if="mode === 'voice'" @start="startVoice" />
        <image v-if="photoPath" class="photo-preview" :src="photoPath" mode="aspectFill" />
        <textarea
          v-model="content"
          class="input-line detail-input"
          maxlength="1000"
          placeholder="补充这条记录"
          auto-height
        />
      </view>

      <view class="section action-row">
        <button class="ego-button" @tap="save">保存</button>
        <button class="ego-button ghost-button" @tap="back">返回</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onLoad } from "@dcloudio/uni-app";
import { ref } from "vue";
import NavBar from "../../components/NavBar.vue";
import VoiceInput from "../../components/VoiceInput.vue";
import { createRecord, getRecord } from "../../api/record";
import { getLocalRecord, saveLocalRecord } from "../../utils/localRecords";

const mode = ref("text");
const recordId = ref("");
const photoPath = ref("");
const content = ref("");
const loadState = ref("ready");

async function loadRecord(id) {
  loadState.value = "loading";
  if (id.startsWith("local-")) {
    const localRecord = getLocalRecord(id);
    if (localRecord) {
      mode.value = localRecord.content_type || "text";
      content.value = localRecord.content || "";
      photoPath.value = localRecord.media_url || "";
      loadState.value = "ready";
      return;
    }
    loadState.value = "missing";
    return;
  }

  try {
    const record = await getRecord(id);
    mode.value = record.content_type || "text";
    content.value = record.content || "";
    photoPath.value = record.media_url || "";
    loadState.value = "ready";
  } catch (error) {
    loadState.value = "missing";
  }
}

function startVoice() {
  uni.showToast({
    title: "待接入同声传译插件",
    icon: "none",
  });
}

async function save() {
  const payload = {
    content_type: mode.value,
    content: content.value.trim(),
    media_url: photoPath.value || undefined,
  };
  try {
    await createRecord(payload);
    uni.showToast({ title: "已保存", icon: "none" });
    uni.switchTab({ url: "/pages/index/index" });
  } catch (error) {
    saveLocalRecord({
      id: recordId.value || `local-${Date.now()}`,
      ...payload,
      record_date: new Date().toISOString().slice(0, 10),
      created_at: new Date().toISOString(),
    });
    uni.showToast({ title: "后端未连接，已本地预览", icon: "none" });
    uni.switchTab({ url: "/pages/index/index" });
  }
}

function back() {
  uni.navigateBack();
}

onLoad((options) => {
  mode.value = options.mode || "text";
  recordId.value = options.id || "";
  photoPath.value = options.path ? decodeURIComponent(options.path) : "";
  if (recordId.value) {
    loadRecord(recordId.value);
  }
});
</script>

<style scoped>
.detail-input {
  min-height: 260rpx;
  margin-top: 24rpx;
  line-height: 1.65;
}

.photo-preview {
  width: 100%;
  height: 420rpx;
  border: 1px solid var(--ego-line);
  background: #ebe8df;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
}
</style>
