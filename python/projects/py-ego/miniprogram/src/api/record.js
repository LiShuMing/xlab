import { request } from "./request";
import { buildQuery } from "../utils/query";

export function createRecord(payload) {
  return request({
    url: "/records",
    method: "POST",
    data: payload,
  });
}

export function listRecords(params = {}) {
  return request({
    url: `/records${buildQuery(params)}`,
  });
}

export function getTimeline(month) {
  return request({
    url: `/records/timeline?month=${encodeURIComponent(month)}`,
  });
}

export function getRecord(recordId) {
  return request({
    url: `/records/${recordId}`,
  });
}

export function deleteRecord(recordId) {
  return request({
    url: `/records/${recordId}`,
    method: "DELETE",
  });
}
