const CURRENT_ROLE_KEY = "py_ego_current_role";

export const BUILTIN_ROLES = [
  {
    id: "therapist",
    name: "心理陪护师",
    description: "更温暖、更慢一点，先接住情绪，再一起看见线索。",
  },
  {
    id: "researcher",
    name: "研究助理",
    description: "更结构化，帮助拆问题、找变量、形成下一步假设。",
  },
];

export function getCurrentRoleId() {
  return uni.getStorageSync(CURRENT_ROLE_KEY) || "therapist";
}

export function setCurrentRoleId(roleId) {
  uni.setStorageSync(CURRENT_ROLE_KEY, roleId);
}

export function getRoleName(roleId) {
  return BUILTIN_ROLES.find((role) => role.id === roleId)?.name || roleId;
}
