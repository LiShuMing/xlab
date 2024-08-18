import { scopedStorageKey } from "./authState";

const STORAGE_KEY = "py_ego_local_records";

function readAll() {
  const records = uni.getStorageSync(scopedStorageKey(STORAGE_KEY));
  return Array.isArray(records) ? records : [];
}

function writeAll(records) {
  uni.setStorageSync(scopedStorageKey(STORAGE_KEY), records.slice(0, 50));
}

export function saveLocalRecord(record) {
  const records = readAll().filter((item) => item.id !== record.id);
  writeAll([record, ...records]);
  return record;
}

export function listLocalRecords() {
  return readAll();
}

export function getLocalRecord(recordId) {
  return readAll().find((record) => record.id === recordId) || null;
}
