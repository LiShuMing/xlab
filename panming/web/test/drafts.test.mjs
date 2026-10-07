import { test } from "node:test";
import assert from "node:assert/strict";
import { DraftStore } from "../.test-build/drafts.js";
class Storage {
  values = new Map();
  get length() {
    return this.values.size;
  }
  key(i) {
    return [...this.values.keys()][i] ?? null;
  }
  getItem(k) {
    return this.values.get(k) ?? null;
  }
  setItem(k, v) {
    this.values.set(k, v);
  }
  removeItem(k) {
    this.values.delete(k);
  }
}
const base = { title: "文章", body: "服务器正文", revision: 1 };
test("A save/accept does not clear B branch; reload can recover B", () => {
  const s = new Storage(),
    a = new DraftStore(s, "blog", "a"),
    b = new DraftStore(s, "blog", "b");
  const ad = a.save(base, "文章", "A 正文");
  b.save(base, "文章", "B 正文");
  assert.equal(a.clearSaved(ad), true);
  assert.equal(new DraftStore(s, "blog", "reloaded").list()[0].body, "B 正文");
});
test("saving an older request cannot clear newer local text", () => {
  const s = new Storage(),
    a = new DraftStore(s, "blog", "a");
  const old = a.save(base, "文章", "旧正文");
  a.save(base, "文章", "更新正文");
  assert.equal(a.clearSaved(old), false);
  assert.equal(a.list()[0].body, "更新正文");
});
test("v0.2 draft survives and remains recoverable", () => {
  const s = new Storage();
  s.setItem(
    "panming.draft.blog",
    JSON.stringify({ title: "旧版", body: "不能丢", revision: 2 }),
  );
  const a = new DraftStore(s, "blog", "a");
  assert.equal(a.list()[0].editor_id, "legacy");
  const own = a.save(base, "新稿", "自己的分支");
  a.clearSaved(own);
  assert.equal(a.list()[0].body, "不能丢");
});
test("different articles and corrupted slots are isolated", () => {
  const s = new Storage(),
    a = new DraftStore(s, "blog", "a");
  s.setItem("panming.draft.v3.blog.b", "broken");
  new DraftStore(s, "other", "c").save(base, "其他", "正文");
  assert.deepEqual(a.list(), []);
  assert.equal(s.getItem("panming.draft.v3.blog.b"), "broken");
});
test("quota/storage failure is surfaced, no sibling slot changed", () => {
  const s = new Storage(),
    b = new DraftStore(s, "blog", "b");
  b.save(base, "文章", "B");
  s.setItem = () => {
    throw new Error("QuotaExceededError");
  };
  assert.throws(
    () => new DraftStore(s, "blog", "a").save(base, "文章", "A"),
    /Quota/,
  );
  assert.equal(b.list()[0].body, "B");
});
