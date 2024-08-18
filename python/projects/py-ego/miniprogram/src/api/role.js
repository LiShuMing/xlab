import { request } from "./request";

export function listRoles() {
  return request({
    url: "/roles",
  });
}

export function getCurrentRole() {
  return request({
    url: "/roles/current",
  });
}

export function updateCurrentRole(roleId) {
  return request({
    url: "/roles/current",
    method: "PUT",
    data: { role_id: roleId },
  });
}
