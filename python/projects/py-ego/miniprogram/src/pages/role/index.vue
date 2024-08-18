<template>
  <view class="page-shell">
    <NavBar label="ROLE" :status="currentRoleId" />

    <view class="grid-panel">
      <view class="section">
        <text class="kicker">COMPANION MODE</text>
        <text class="hero-title">角色</text>
        <text class="body-text">选择当前对话的工作方式。角色不会改变你的记录，只改变回应视角。</text>
      </view>

      <view class="section">
        <RoleCard
          v-for="role in roles"
          :key="role.id"
          :role="role"
          :selected="role.id === currentRoleId"
          @select="selectRole"
        />
      </view>

      <view class="section role-footer">
        <view>
          <text class="kicker">CURRENT</text>
          <text class="section-title">{{ currentRoleName }}</text>
        </view>
        <button class="ego-button" @tap="goChat">去对话</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import NavBar from "../../components/NavBar.vue";
import RoleCard from "../../components/RoleCard.vue";
import { getCurrentRole, listRoles, updateCurrentRole } from "../../api/role";
import { BUILTIN_ROLES, getCurrentRoleId, setCurrentRoleId } from "../../utils/roles";
import { requireLogin } from "../../utils/authState";

const currentRoleId = ref(getCurrentRoleId());
const roles = ref(BUILTIN_ROLES);
const currentRoleName = computed(() => {
  return roles.value.find((role) => role.id === currentRoleId.value)?.name || currentRoleId.value;
});

async function loadRoles() {
  if (!requireLogin()) {
    return;
  }
  currentRoleId.value = getCurrentRoleId();
  try {
    const response = await listRoles();
    roles.value = mergeRoles(response.roles || roles.value);
    const current = await getCurrentRole();
    currentRoleId.value = current.role?.id || getCurrentRoleId();
    setCurrentRoleId(currentRoleId.value);
  } catch (error) {
    // Keep built-in roles for local UI development.
  }
}

async function selectRole(role) {
  const previousRoleId = currentRoleId.value;
  currentRoleId.value = role.id;
  setCurrentRoleId(role.id);
  uni.showToast({ title: `已切换到${role.name}`, icon: "none" });
  try {
    await updateCurrentRole(role.id);
  } catch (error) {
    if (currentRoleId.value === previousRoleId) {
      return;
    }
  }
}

function goChat() {
  uni.switchTab({ url: "/pages/chat/index" });
}

function mergeRoles(remoteRoles) {
  return remoteRoles.map((role) => {
    const builtin = BUILTIN_ROLES.find((item) => item.id === role.id);
    return {
      ...builtin,
      ...role,
      description: role.description || builtin?.description || "",
    };
  });
}

onMounted(loadRoles);
</script>

<style scoped>
.role-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
}
</style>
